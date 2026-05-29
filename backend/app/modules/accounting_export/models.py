"""AccountingExport ORM model."""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK, JsonB


class AccountingExportStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class AccountingExportFormat(str, enum.Enum):
    sage = "sage"
    cegid = "cegid"
    ebp = "ebp"
    generic_csv = "generic_csv"


class AccountingExport(Base):
    __tablename__ = "accounting_export"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        # Stored as text on SQLite, native UUID on PostgreSQL
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid_lib.uuid4()),
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    period_start: Mapped[date] = mapped_column(
        # Date stored via String for SQLite compat; PostgreSQL uses native Date
        String(10),
        nullable=False,
    )
    period_end: Mapped[date] = mapped_column(
        String(10),
        nullable=False,
    )

    format: Mapped[str] = mapped_column(String(20), nullable=False, default="generic_csv")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    file_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exported_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    record_counts: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_accounting_export_garage_id", "garage_id"),
        Index("ix_accounting_export_garage_period", "garage_id", "period_start", "period_end"),
    )
