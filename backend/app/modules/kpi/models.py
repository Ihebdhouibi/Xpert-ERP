from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, Date, DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK, JsonB


class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshot"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    kpi_code: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    meta: Mapped[Optional[Any]] = mapped_column(JsonB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "garage_id", "snapshot_date", "kpi_code",
            name="uq_kpi_snapshot_garage_date_code",
        ),
        Index("ix_kpi_snapshot_garage_code_date", "garage_id", "kpi_code", "snapshot_date"),
        Index("ix_kpi_snapshot_garage_date", "garage_id", "snapshot_date"),
    )
