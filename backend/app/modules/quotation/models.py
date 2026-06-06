"""Quotation and QuotationLine ORM models."""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class QuotationStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    converted = "converted"  # converted to invoice


class LineKind(str, enum.Enum):
    labor = "labor"
    part = "part"
    service = "service"
    other = "other"


class Quotation(Base):
    __tablename__ = "quotation"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4())
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("vehicle.id", ondelete="RESTRICT"), nullable=True
    )
    repair_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Document number assigned by sequence service when first sent (not draft)
    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus, name="quotation_status_enum"),
        nullable=False,
        default=QuotationStatus.draft,
        server_default="draft",
    )

    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Money totals in minor units (e.g. cents)
    subtotal_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    discount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    vat_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optimistic concurrency
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list[QuotationLine]] = relationship(
        "QuotationLine", back_populates="quotation", cascade="all, delete-orphan", order_by="QuotationLine.id"
    )

    __table_args__ = (
        Index("ix_quotation_garage_id", "garage_id"),
        Index("ix_quotation_customer_id", "customer_id"),
        Index("ix_quotation_status", "status"),
        CheckConstraint(
            "status IN ('draft','sent','approved','rejected','expired','converted')",
            name="ck_quotation_status",
        ),
    )


class QuotationLine(Base):
    __tablename__ = "quotation_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    quotation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quotation.id", ondelete="CASCADE"), nullable=False
    )

    kind: Mapped[LineKind] = mapped_column(
        String(20),
        nullable=False,
        default=LineKind.service,
    )
    part_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0"
    )

    # Computed and stored for reporting
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    __table_args__ = (Index("ix_quotation_line_quotation_id", "quotation_id"),)

    quotation: Mapped[Quotation] = relationship("Quotation", back_populates="lines")
