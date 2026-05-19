from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Who performed the action (NULL for system/scheduler actions)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Which app module produced this entry (auth, repair_order, payment, …)
    component: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Verb: create, update, delete, login, logout, permission_change, …
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Entity touched by this action
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Before/after snapshots (JSONB — stripped of sensitive fields by writer)
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]

    # Human-readable reason / comment supplied by the actor
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Traceability: X-Request-ID header value, propagated from middleware
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # IP address of the originating request
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Approximate duration of the operation in milliseconds
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
