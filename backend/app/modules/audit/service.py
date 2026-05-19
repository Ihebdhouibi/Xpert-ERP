"""Audit log writer service.

Usage (fire-and-forget from any endpoint):

    from app.modules.audit.service import audit

    await audit(
        db=db,
        garage_id=user.garage_id,
        user_id=None,       # int internal user id (not public_id)
        component="auth",
        action="login",
        entity_type="app_user",
        entity_id=user_db_id,
        new_value={"email": user.email},
        request_id=request.headers.get("X-Request-ID"),
    )
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.audit.models import AuditLog

logger = get_logger("audit")

# Fields that must never appear in audit snapshots
_REDACTED_FIELDS = frozenset(
    {
        "password",
        "password_hash",
        "password_reset_token_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "secret_key",
    }
)


def _redact(data: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not data:
        return data
    return {
        k: "[REDACTED]" if k in _REDACTED_FIELDS else v
        for k, v in data.items()
    }


async def audit(
    db: AsyncSession,
    *,
    garage_id: int,
    component: str,
    action: str,
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    old_value: Optional[dict[str, Any]] = None,
    new_value: Optional[dict[str, Any]] = None,
    reason: Optional[str] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Write a single audit log entry. Flushes but does NOT commit — caller owns the transaction."""
    entry = AuditLog(
        garage_id=garage_id,
        user_id=user_id,
        component=component,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=_redact(old_value),
        new_value=_redact(new_value),
        reason=reason,
        request_id=request_id,
        ip_address=ip_address,
        duration_ms=duration_ms,
    )
    db.add(entry)
    try:
        await db.flush()
    except Exception:
        logger.error(
            "audit_write_failed",
            garage_id=garage_id,
            component=component,
            action=action,
        )
        raise
