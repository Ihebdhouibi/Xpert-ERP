"""
SettingsService — Redis-cached, DB-backed runtime configuration.

Lookup order for get_setting(key, garage_id):
  1. Redis cache  → return immediately on hit
  2. DB row with matching (garage_id, key)
  3. DB row with (garage_id=0, key)   — global default override
  4. pydantic-settings env value       — fallback to Settings class
  5. caller-supplied default           — last resort

Values are always stored and returned as strings.  Use the typed
helpers (get_int, get_bool, get_float) for automatic coercion.

Cache key pattern: cfg:<garage_id>:<key>
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.config.models import GarageSetting

logger = get_logger("config.service")

_CACHE_PREFIX = "cfg"
_GLOBAL_GARAGE_ID = 0


class SettingsService:
    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self._db = db
        self._redis = redis
        self._env = get_settings()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_key(self, key: str, garage_id: int) -> str:
        return f"{_CACHE_PREFIX}:{garage_id}:{key}"

    def _ttl(self) -> int:
        return self._env.cfg_config_cache_ttl_seconds

    async def _from_db(self, key: str, garage_id: int) -> Optional[str]:
        """Return value from DB, checking per-garage then global."""
        ids_to_try = [garage_id] if garage_id != _GLOBAL_GARAGE_ID else [_GLOBAL_GARAGE_ID]
        if garage_id != _GLOBAL_GARAGE_ID:
            ids_to_try.append(_GLOBAL_GARAGE_ID)

        for gid in ids_to_try:
            result = await self._db.execute(
                select(GarageSetting).where(
                    GarageSetting.garage_id == gid,
                    GarageSetting.key == key,
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                return row.value
        return None

    def _from_env(self, key: str) -> Optional[str]:
        """Return the env/pydantic-settings value for key (case-insensitive)."""
        value = getattr(self._env, key.lower(), None)
        if value is None:
            return None
        return str(value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_setting(
        self,
        key: str,
        garage_id: int = _GLOBAL_GARAGE_ID,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Return the effective string value for a CFG_* key."""
        cache_key = self._cache_key(key, garage_id)

        cached = await self._redis.get(cache_key)
        if cached is not None:
            return cached

        value = await self._from_db(key, garage_id)
        if value is None:
            value = self._from_env(key)
        if value is None:
            value = default

        if value is not None:
            try:
                await self._redis.setex(cache_key, self._ttl(), value)
            except Exception:
                logger.warning("config_cache_write_failed", key=key)

        return value

    async def get_int(
        self, key: str, garage_id: int = _GLOBAL_GARAGE_ID, default: Optional[int] = None
    ) -> Optional[int]:
        raw = await self.get_setting(key, garage_id)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            logger.warning("config_int_cast_failed", key=key, value=raw)
            return default

    async def get_bool(
        self, key: str, garage_id: int = _GLOBAL_GARAGE_ID, default: Optional[bool] = None
    ) -> Optional[bool]:
        raw = await self.get_setting(key, garage_id)
        if raw is None:
            return default
        return raw.strip().lower() in ("true", "1", "yes", "on")

    async def get_float(
        self, key: str, garage_id: int = _GLOBAL_GARAGE_ID, default: Optional[float] = None
    ) -> Optional[float]:
        raw = await self.get_setting(key, garage_id)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            logger.warning("config_float_cast_failed", key=key, value=raw)
            return default

    async def upsert_setting(
        self,
        key: str,
        value: str,
        garage_id: int = _GLOBAL_GARAGE_ID,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> GarageSetting:
        result = await self._db.execute(
            select(GarageSetting).where(
                GarageSetting.garage_id == garage_id,
                GarageSetting.key == key,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = GarageSetting(
                garage_id=garage_id,
                key=key,
                value=value,
                description=description,
                updated_by=user_id,
            )
            self._db.add(row)
        else:
            row.value = value
            row.updated_by = user_id
            row.updated_at = datetime.now(UTC)
            if description is not None:
                row.description = description

        await self._db.commit()
        await self._db.refresh(row)
        await self._invalidate(key, garage_id)
        logger.info("config_setting_upserted", key=key, garage_id=garage_id)
        return row

    async def delete_setting(
        self, key: str, garage_id: int = _GLOBAL_GARAGE_ID
    ) -> bool:
        result = await self._db.execute(
            select(GarageSetting).where(
                GarageSetting.garage_id == garage_id,
                GarageSetting.key == key,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._db.delete(row)
        await self._db.commit()
        await self._invalidate(key, garage_id)
        logger.info("config_setting_deleted", key=key, garage_id=garage_id)
        return True

    async def list_settings(
        self, garage_id: int = _GLOBAL_GARAGE_ID
    ) -> list[GarageSetting]:
        result = await self._db.execute(
            select(GarageSetting)
            .where(GarageSetting.garage_id == garage_id)
            .order_by(GarageSetting.key)
        )
        return list(result.scalars().all())

    async def _invalidate(self, key: str, garage_id: int) -> None:
        try:
            await self._redis.delete(self._cache_key(key, garage_id))
        except Exception:
            logger.warning("config_cache_invalidate_failed", key=key)


def get_settings_service(db: AsyncSession, redis: Redis) -> SettingsService:
    """Convenience factory used in FastAPI dependencies."""
    return SettingsService(db=db, redis=redis)
