from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class SupplierStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class Supplier(Base):
    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    average_delivery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reliability_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    status: Mapped[SupplierStatus] = mapped_column(
        String(20), nullable=False, default=SupplierStatus.active
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    prices: Mapped[list[SupplierPartPrice]] = relationship(
        "SupplierPartPrice", back_populates="supplier", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_supplier_public_id"),
        Index("ix_supplier_garage_id", "garage_id"),
        Index("ix_supplier_garage_status", "garage_id", "status"),
    )


class SupplierPartPrice(Base):
    __tablename__ = "supplier_part_price"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="CASCADE"), nullable=False
    )
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MAD")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="prices")

    __table_args__ = (
        Index("ix_spp_supplier_id", "supplier_id"),
        Index("ix_spp_part_id", "part_id"),
        Index("ix_spp_supplier_part", "supplier_id", "part_id"),
        Index("ix_spp_part_effective", "part_id", "effective_from"),
    )
