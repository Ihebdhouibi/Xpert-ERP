from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK


class StockMovementType(str, enum.Enum):
    in_ = "in"
    out = "out"
    adjustment = "adjustment"
    reservation = "reservation"
    release = "release"

    @classmethod
    def _missing_(cls, value: object) -> Optional[StockMovementType]:
        for member in cls:
            if member.value == value:
                return member
        return None


class StockLevel(Base):
    __tablename__ = "stock_level"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    part_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="CASCADE"), nullable=False
    )
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("garage_id", "part_id", name="uq_stock_level_garage_part"),
        Index("ix_stock_level_garage_id", "garage_id"),
        Index("ix_stock_level_garage_part", "garage_id", "part_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    part_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, name="stock_movement_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ref_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("quantity != 0", name="ck_stock_movement_qty_nonzero"),
        Index("ix_stock_movement_garage_part", "garage_id", "part_id"),
        Index("ix_stock_movement_garage_created", "garage_id", "created_at"),
        Index("ix_stock_movement_ref", "ref_type", "ref_id"),
    )


class LowStockAlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class LowStockAlert(Base):
    __tablename__ = "low_stock_alert"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    part_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="CASCADE"), nullable=False
    )
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    suggested_reorder_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[LowStockAlertStatus] = mapped_column(
        Enum(LowStockAlertStatus, name="low_stock_alert_status",
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=LowStockAlertStatus.open,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_low_stock_alert_garage", "garage_id"),
        Index("ix_low_stock_alert_part", "part_id"),
        Index("ix_low_stock_alert_status", "garage_id", "status"),
    )
