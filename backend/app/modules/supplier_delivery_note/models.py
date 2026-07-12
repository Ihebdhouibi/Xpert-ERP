"""Supplier delivery note (Bon de livraison fournisseur) ORM models.

A received BL, always linked to a purchase order. Its ``bl_number`` is the
correlation key with the supplier invoice for the eventual 3-way match. Lines
map to PO lines and drive stock-in + the PO's ``quantity_received`` rollup.
"""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
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


class SupplierDeliveryNoteStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    cancelled = "cancelled"


class SupplierDeliveryNote(Base):
    __tablename__ = "supplier_delivery_note"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Always linked to exactly one purchase order.
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # The supplier's BL number — correlation key with the facture. Nullable
    # because OCR may not read it; unique per (garage, supplier) when present.
    bl_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bl_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Direct link to the supplier invoice that covers this BL (set when
    # the invoice is created from the parent PO).
    supplier_invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("supplier_invoice.id", ondelete="SET NULL"), nullable=True
    )

    # The uploaded GED document this BL was created from (OCR source).
    document_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SupplierDeliveryNoteStatus.confirmed.value
    )
    has_discrepancy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    received_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    lines: Mapped[list["SupplierDeliveryNoteLine"]] = relationship(
        "SupplierDeliveryNoteLine",
        back_populates="delivery_note",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "garage_id", "supplier_id", "bl_number", name="uq_sdn_garage_supplier_blnumber"
        ),
        Index("ix_sdn_garage_po", "garage_id", "purchase_order_id"),
    )


class SupplierDeliveryNoteLine(Base):
    __tablename__ = "supplier_delivery_note_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    supplier_delivery_note_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("supplier_delivery_note.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The PO line this delivers (nullable for an extra item not on the PO).
    po_line_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    part_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Numeric so decimal delivered quantities (e.g. 0.20) are stored faithfully.
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit_price_ht: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # ok / over (qty > remaining) / extra (not on the PO)
    match_flag: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")

    # Fields captured from the BL itself (the supplier's own line), so the
    # delivery note is recorded faithfully and linked field-by-field.
    code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pu_brut: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    pu_net: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    montant_ht: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    delivery_note: Mapped[SupplierDeliveryNote] = relationship(
        "SupplierDeliveryNote", back_populates="lines"
    )

    __table_args__ = (
        Index("ix_sdn_line_sdn", "supplier_delivery_note_id"),
    )
