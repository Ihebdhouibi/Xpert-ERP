"""
Unit tests for SettingsService.

All external dependencies (DB, Redis, pydantic-settings) are replaced
with lightweight in-memory fakes so no infrastructure is required.
"""
from __future__ import annotations

import pytest

from app.modules.config.models import GarageSetting
from app.modules.config.service import SettingsService, _CACHE_PREFIX, _GLOBAL_GARAGE_ID


class _FakeEnv:
    """Simple env stub — only exposes explicitly set attributes."""

    cfg_config_cache_ttl_seconds: int = 60

    def __init__(self, **overrides: object) -> None:
        for k, v in overrides.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Minimal async Redis fake — stores values in a plain dict."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._deleted.append(key)


class _FakeRow:
    """Mimics a GarageSetting ORM row."""

    def __init__(self, key: str, value: str, garage_id: int = 0) -> None:
        self.id = 1
        self.garage_id = garage_id
        self.key = key
        self.value = value
        self.description = None
        self.updated_at = None
        self.updated_by = None


class _FakeScalarResult:
    def __init__(self, row: _FakeRow | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> _FakeRow | None:
        return self._row

    def scalars(self) -> _FakeScalarResult:
        return self

    def all(self) -> list[_FakeRow]:
        return [self._row] if self._row else []


class _FakeDB:
    """Minimal async SQLAlchemy session fake."""

    def __init__(self, rows: list[_FakeRow] | None = None) -> None:
        self._rows: list[_FakeRow] = rows or []
        self.committed = False
        self.added: list[object] = []
        self.deleted: list[object] = []

    async def execute(self, stmt: object) -> _FakeScalarResult:
        # Return the first matching row; tests control the store directly.
        if self._rows:
            return _FakeScalarResult(self._rows[0])
        return _FakeScalarResult(None)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, GarageSetting):
            self._rows.append(obj)  # type: ignore[arg-type]

    async def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def redis() -> _FakeRedis:
    return _FakeRedis()


@pytest.fixture
def db() -> _FakeDB:
    return _FakeDB()


def _svc(db: _FakeDB, redis: _FakeRedis, env_overrides: dict | None = None) -> SettingsService:
    svc = SettingsService.__new__(SettingsService)
    svc._db = db  # type: ignore[assignment]
    svc._redis = redis  # type: ignore[assignment]
    svc._env = _FakeEnv(**(env_overrides or {}))
    return svc


# ---------------------------------------------------------------------------
# get_setting tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_setting_returns_cached_value(redis: _FakeRedis, db: _FakeDB) -> None:
    redis._store[f"{_CACHE_PREFIX}:0:cfg_foo"] = "cached_val"
    svc = _svc(db, redis)
    result = await svc.get_setting("cfg_foo")
    assert result == "cached_val"


@pytest.mark.asyncio
async def test_get_setting_reads_db_and_caches(redis: _FakeRedis) -> None:
    db = _FakeDB(rows=[_FakeRow("cfg_foo", "db_val")])
    svc = _svc(db, redis)
    result = await svc.get_setting("cfg_foo")
    assert result == "db_val"
    # Value should now be in cache
    assert redis._store.get(f"{_CACHE_PREFIX}:0:cfg_foo") == "db_val"


@pytest.mark.asyncio
async def test_get_setting_falls_back_to_env(redis: _FakeRedis, db: _FakeDB) -> None:
    svc = _svc(db, redis, env_overrides={"cfg_bar": 42})
    result = await svc.get_setting("cfg_bar")
    assert result == "42"


@pytest.mark.asyncio
async def test_get_setting_returns_default_when_nothing_found(
    redis: _FakeRedis, db: _FakeDB
) -> None:
    svc = _svc(db, redis)
    result = await svc.get_setting("cfg_nonexistent", default="fallback")
    assert result == "fallback"


@pytest.mark.asyncio
async def test_get_setting_none_when_truly_missing(redis: _FakeRedis, db: _FakeDB) -> None:
    svc = _svc(db, redis)
    result = await svc.get_setting("cfg_nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# Typed helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_int(redis: _FakeRedis) -> None:
    db = _FakeDB(rows=[_FakeRow("cfg_num", "99")])
    svc = _svc(db, redis)
    assert await svc.get_int("cfg_num") == 99


@pytest.mark.asyncio
async def test_get_int_invalid_returns_default(redis: _FakeRedis) -> None:
    db = _FakeDB(rows=[_FakeRow("cfg_num", "not_a_number")])
    svc = _svc(db, redis)
    assert await svc.get_int("cfg_num", default=7) == 7


@pytest.mark.asyncio
async def test_get_bool_true_values(redis: _FakeRedis) -> None:
    for truthy in ("true", "True", "1", "yes", "on"):
        db = _FakeDB(rows=[_FakeRow("cfg_flag", truthy)])
        svc = _svc(db, redis)
        assert await svc.get_bool("cfg_flag") is True


@pytest.mark.asyncio
async def test_get_bool_false_values(redis: _FakeRedis) -> None:
    for falsy in ("false", "0", "no", "off"):
        db = _FakeDB(rows=[_FakeRow("cfg_flag", falsy)])
        svc = _svc(db, redis)
        assert await svc.get_bool("cfg_flag") is False


@pytest.mark.asyncio
async def test_get_float(redis: _FakeRedis) -> None:
    db = _FakeDB(rows=[_FakeRow("cfg_rate", "3.14")])
    svc = _svc(db, redis)
    assert await svc.get_float("cfg_rate") == pytest.approx(3.14)


# ---------------------------------------------------------------------------
# upsert_setting tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_creates_new_row(redis: _FakeRedis, db: _FakeDB) -> None:
    svc = _svc(db, redis)
    row = await svc.upsert_setting("cfg_new", "hello", user_id=1)
    assert row.value == "hello"
    assert db.committed is True
    # Cache for this key must have been invalidated
    assert f"{_CACHE_PREFIX}:0:cfg_new" in redis._deleted


@pytest.mark.asyncio
async def test_upsert_updates_existing_row(redis: _FakeRedis) -> None:
    existing = _FakeRow("cfg_existing", "old_val")
    db = _FakeDB(rows=[existing])
    svc = _svc(db, redis)
    row = await svc.upsert_setting("cfg_existing", "new_val")
    assert row.value == "new_val"
    assert db.committed is True


# ---------------------------------------------------------------------------
# delete_setting tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_existing_setting(redis: _FakeRedis) -> None:
    existing = _FakeRow("cfg_del", "bye")
    db = _FakeDB(rows=[existing])
    svc = _svc(db, redis)
    deleted = await svc.delete_setting("cfg_del")
    assert deleted is True
    assert db.committed is True
    assert f"{_CACHE_PREFIX}:0:cfg_del" in redis._deleted


@pytest.mark.asyncio
async def test_delete_missing_setting_returns_false(
    redis: _FakeRedis, db: _FakeDB
) -> None:
    svc = _svc(db, redis)
    deleted = await svc.delete_setting("cfg_ghost")
    assert deleted is False


# ---------------------------------------------------------------------------
# Cache key format
# ---------------------------------------------------------------------------

def test_cache_key_format() -> None:
    svc = _svc(_FakeDB(), _FakeRedis())
    assert svc._cache_key("cfg_foo", 42) == "cfg:42:cfg_foo"
    assert svc._cache_key("cfg_foo", _GLOBAL_GARAGE_ID) == "cfg:0:cfg_foo"
