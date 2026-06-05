"""DeliveryNote and DeliveryNoteLine ORM models.

A Bon de Livraison (BL) represents parts / accessories sold directly to a
customer without an originating repair order.  The full lifecycle is:

    draft → issued → delivered | cancelled

An issued BL can be converted to an Invoice via the convert-to-invoice action.
"""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class DeliveryNoteStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"          # doc_number assigned, lines locked
    delivered = "delivered"    # goods handed to customer
    cancelled = "cancelled"


class DeliveryNoteLineKind(str, enum.Enum):
    part = "part"
    accessory = "accessory"
    service = "service"
    other = "other"


class DeliveryNote(Base):
    __tablename__ = "delivery_note"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4())
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("vehicle.id", ondelete="SET NULL"), nullable=True
    )
    # If this BL was converted to an invoice, record the link
    invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True
    )

    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[DeliveryNoteStatus] = mapped_column(
        Enum(DeliveryNoteStatus, name="delivery_note_status_enum"),
        nullable=False,
        default=DeliveryNoteStatus.draft,
        server_default="draft",
    )

    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Totals in minor currency units (cents)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    vat_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TND")
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

    lines: Mapped[list["DeliveryNoteLine"]] = relationship(
        "DeliveryNoteLine", back_populates="delivery_note", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        Index("ix_dn_garage_id", "garage_id"),
        Index("ix_dn_customer_id", "customer_id"),
        Index("ix_dn_status", "status"),
        Index("ix_dn_garage_customer", "garage_id", "customer_id"),
    )


class DeliveryNoteLine(Base):
    __tablename__ = "delivery_note_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    delivery_note_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_note.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[DeliveryNoteLineKind] = mapped_column(
        Enum(DeliveryNoteLineKind, name="dn_line_kind_enum"),
        nullable=False,
        default=DeliveryNoteLineKind.part,
        server_default="part",
    )
    part_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    delivery_note: Mapped["DeliveryNote"] = relationship("DeliveryNote", back_populates="lines")

    __table_args__ = (
        Index("ix_dn_line_delivery_note_id", "delivery_note_id"),
    )
