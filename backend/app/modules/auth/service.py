"""Auth service — hashing, JWT, token lifecycle, login/logout/reset."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.auth import repository as repo
from app.modules.auth.models import AppUser
from app.modules.auth.schemas import LoginResponse, UserOut

logger = get_logger("auth")

# Argon2id with OWASP-recommended parameters
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

_DENY_LIST_PREFIX = "token:deny:"
_REFRESH_PREFIX = "token:refresh:"


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    subject: str,
    garage_id: int,
    roles: list[str],
    permissions: list[str],
    user_id: int = 0,
) -> tuple[str, int]:
    """Return (encoded_jwt, expires_in_seconds)."""
    cfg = get_settings()
    expire_seconds = cfg.access_token_expire_minutes * 60
    expire = _utcnow() + timedelta(seconds=expire_seconds)
    payload: dict[str, Any] = {
        "sub": subject,
        "uid": user_id,
        "gid": garage_id,
        "roles": roles,
        "perms": permissions,
        "exp": expire,
        "iat": _utcnow(),
        "type": "access",
    }
    token = jwt.encode(payload, cfg.secret_key, algorithm=cfg.algorithm)
    return token, expire_seconds


def create_refresh_token(subject: str) -> tuple[str, str]:
    """Return (encoded_jwt, jti).  jti is stored in Redis."""
    cfg = get_settings()
    jti = secrets.token_urlsafe(32)
    expire = _utcnow() + timedelta(days=cfg.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "exp": expire,
        "iat": _utcnow(),
        "type": "refresh",
    }
    token = jwt.encode(payload, cfg.secret_key, algorithm=cfg.algorithm)
    return token, jti


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    cfg = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token, cfg.secret_key, algorithms=[cfg.algorithm]
    )
    if payload.get("type") != expected_type:
        raise JWTError("Wrong token type")
    return payload


# ---------------------------------------------------------------------------
# Redis token lifecycle
# ---------------------------------------------------------------------------

async def _deny_list_token(redis: Redis, jti: str, ttl_seconds: int) -> None:
    key = f"{_DENY_LIST_PREFIX}{jti}"
    await redis.setex(key, ttl_seconds, "1")


async def is_token_denied(redis: Redis, jti: str) -> bool:
    return bool(await redis.exists(f"{_DENY_LIST_PREFIX}{jti}"))


async def store_refresh_jti(redis: Redis, jti: str, subject: str, ttl_seconds: int) -> None:
    key = f"{_REFRESH_PREFIX}{jti}"
    await redis.setex(key, ttl_seconds, subject)


async def consume_refresh_jti(redis: Redis, jti: str) -> Optional[str]:
    """Return subject and atomically delete — rotation pattern."""
    key = f"{_REFRESH_PREFIX}{jti}"
    subject = await redis.getdel(key)
    if subject is None:
        return None
    return subject.decode() if isinstance(subject, bytes) else subject


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def login(
    db: AsyncSession,
    redis: Redis,
    email: str,
    password: str,
    garage_id: int,
) -> LoginResponse:
    cfg = get_settings()

    user = await repo.get_user_by_email(db, garage_id, email)

    # Constant-time path even if user not found (prevents user enumeration)
    dummy_hash = "$argon2id$v=19$m=65536,t=2,p=1$dGVzdA$dGVzdA"
    password_ok = False
    if user:
        password_ok = verify_password(password, user.password_hash)

    if not user or not password_ok:
        if user:
            count = await repo.increment_failed_logins(db, user.id)
            if count >= cfg.auth_max_failed_attempts:
                lockout_until = _utcnow() + timedelta(minutes=cfg.auth_lockout_minutes)
                await repo.lock_user(db, user.id, lockout_until)
                await db.commit()
                logger.warning("account_locked", user_id=user.id, garage_id=garage_id)
            else:
                await db.commit()
        raise ValueError("Invalid credentials")

    if user.status == "locked":
        if user.locked_until and user.locked_until > _utcnow():
            raise ValueError("Account is locked. Try again later.")
        # Lockout expired — auto-unlock
        await repo.reset_failed_logins(db, user.id)

    if user.status == "inactive":
        raise ValueError("Account is inactive.")

    # Load roles + permissions
    user_with_roles = await repo.get_user_with_roles(db, user.id)
    if user_with_roles is None:
        raise ValueError("User not found")

    roles = repo.collect_role_codes(user_with_roles)
    permissions = repo.collect_permissions(user_with_roles)
    subject = str(user.public_id)

    access_token, expires_in = create_access_token(subject, garage_id, roles, permissions, user_id=user.id)
    refresh_token, jti = create_refresh_token(subject)

    refresh_ttl = cfg.refresh_token_expire_days * 86400
    await store_refresh_jti(redis, jti, subject, refresh_ttl)

    # Rehash if parameters changed
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    await repo.reset_failed_logins(db, user.id)
    await db.commit()

    logger.info("login_success", user_id=user.id, garage_id=garage_id)

    user_out = UserOut(
        id=subject,
        garage_id=user.garage_id,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value,
        roles=roles,
        permissions=permissions,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=user_out,
    )


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

async def refresh(
    db: AsyncSession,
    redis: Redis,
    refresh_token_str: str,
) -> LoginResponse:
    cfg = get_settings()
    try:
        payload = decode_token(refresh_token_str, expected_type="refresh")
    except JWTError as exc:
        raise ValueError("Invalid refresh token") from exc

    jti: str = payload.get("jti", "")
    subject: str = payload.get("sub", "")

    stored_subject = await consume_refresh_jti(redis, jti)
    if stored_subject is None or stored_subject != subject:
        # Possible token reuse — deny-list the entire subject's tokens
        logger.warning("refresh_token_reuse_detected", subject=subject)
        raise ValueError("Invalid or already-used refresh token")

    user = await repo.get_user_by_public_id(db, subject)
    if user is None or user.status != "active":
        raise ValueError("User not found or inactive")

    user_with_roles = await repo.get_user_with_roles(db, user.id)
    if user_with_roles is None:
        raise ValueError("User not found")

    roles = repo.collect_role_codes(user_with_roles)
    permissions = repo.collect_permissions(user_with_roles)

    access_token, expires_in = create_access_token(
        subject, user.garage_id, roles, permissions, user_id=user.id
    )
    new_refresh_token, new_jti = create_refresh_token(subject)
    refresh_ttl = cfg.refresh_token_expire_days * 86400
    await store_refresh_jti(redis, new_jti, subject, refresh_ttl)

    user_out = UserOut(
        id=subject,
        garage_id=user.garage_id,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value,
        roles=roles,
        permissions=permissions,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
        user=user_out,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

async def logout(redis: Redis, refresh_token_str: str) -> None:
    cfg = get_settings()
    try:
        payload = decode_token(refresh_token_str, expected_type="refresh")
    except JWTError:
        return  # Already invalid — nothing to revoke

    jti: str = payload.get("jti", "")
    if jti:
        # Consume (delete) the refresh JTI so it can never be reused
        await consume_refresh_jti(redis, jti)
        # Also deny-list for the remaining TTL of the token
        exp = payload.get("exp")
        if exp:
            remaining = int(exp) - int(_utcnow().timestamp())
            if remaining > 0:
                await _deny_list_token(redis, jti, remaining)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

async def request_password_reset(
    db: AsyncSession,
    garage_id: int,
    email: str,
) -> Optional[str]:
    """Returns the raw reset token (caller sends it via email). None if user not found."""
    cfg = get_settings()
    user = await repo.get_user_by_email(db, garage_id, email)
    if not user or user.status == "inactive":
        return None

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = _utcnow() + timedelta(minutes=cfg.password_reset_expiry_minutes)

    await repo.set_password_reset_token(db, user.id, token_hash, expires_at)
    await db.commit()
    return raw_token


async def confirm_password_reset(
    db: AsyncSession,
    garage_id: int,
    email: str,
    raw_token: str,
    new_password: str,
) -> None:
    user = await repo.get_user_by_email(db, garage_id, email)
    if not user:
        raise ValueError("Invalid reset request")

    if not user.password_reset_token_hash or not user.password_reset_expires_at:
        raise ValueError("No pending password reset")

    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    if not secrets.compare_digest(expected_hash, user.password_reset_token_hash):
        raise ValueError("Invalid reset token")

    if user.password_reset_expires_at < _utcnow():
        raise ValueError("Reset token has expired")

    new_hash = hash_password(new_password)
    await repo.update_password(db, user.id, new_hash)
    await db.commit()
    logger.info("password_reset_success", user_id=user.id)
