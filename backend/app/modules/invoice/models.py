"""Invoice and InvoiceLine ORM models."""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"       # locked, doc_number assigned
    partial = "partial"     # partially paid
    paid = "paid"           # fully paid
    cancelled = "cancelled"


class InvoiceLineKind(str, enum.Enum):
    labor = "labor"
    part = "part"
    service = "service"
    other = "other"


class Invoice(Base):
    __tablename__ = "invoice"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
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

    # Source quotation — set when converted from a quotation
    quotation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("quotation.id", ondelete="SET NULL"), nullable=True
    )

    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status_enum"),
        nullable=False,
        default=InvoiceStatus.draft,
        server_default="draft",
    )

    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Money in minor units
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    vat_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    # Payment tracking — updated by payment service (#31)
    paid_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    outstanding_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    is_exported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    lines: Mapped[list[InvoiceLine]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.id",
    )
    payments: Mapped[list["Payment"]] = relationship(  # type: ignore[name-defined]
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="Payment.id",
    )
    credit_notes: Mapped[list["CreditNote"]] = relationship(  # type: ignore[name-defined]
        "CreditNote",
        back_populates="invoice",
        order_by="CreditNote.id",
    )

    __table_args__ = (
        Index("ix_invoice_garage_id", "garage_id"),
        Index("ix_invoice_customer_id", "customer_id"),
        Index("ix_invoice_status", "status"),
        Index("ix_invoice_quotation_id", "quotation_id"),
        CheckConstraint(
            "status IN ('draft','issued','partial','paid','cancelled')",
            name="ck_invoice_status",
        ),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[InvoiceLineKind] = mapped_column(
        String(20),
        nullable=False,
        default=InvoiceLineKind.service,
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
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    __table_args__ = (Index("ix_invoice_line_invoice_id", "invoice_id"),)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")
