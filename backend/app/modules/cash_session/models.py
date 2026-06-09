"""CashSession ORM model."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class CashSessionStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class CashSession(Base):
    __tablename__ = "cash_session"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[CashSessionStatus] = mapped_column(
        Enum(CashSessionStatus, name="cash_session_status_enum"),
        nullable=False,
        default=CashSessionStatus.open,
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    opened_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Cash float placed in the drawer at open time (change fund), in minor units
    opening_float: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0", default=0
    )

    # Computed on close: opening_float + sum of cash payments in this session
    expected_total_cash: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Physical count entered by closer
    counted_total_cash: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # counted - expected (positive = surplus, negative = shortage)
    difference: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Optional reason required when |difference| > 0 and CFG_CASH_DIFF_REQUIRE_REASON=True
    closing_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    payments: Mapped[list["Payment"]] = relationship(  # type: ignore[name-defined]
        "Payment", back_populates="cash_session", lazy="select"
    )
