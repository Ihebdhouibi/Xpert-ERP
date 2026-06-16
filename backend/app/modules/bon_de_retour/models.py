"""Bon de Retour (return note) ORM models.

A *bon de retour* records the **physical** return of parts. It is distinct from the
*avoir* (credit note), which records the **financial** movement.

It applies to two parties:

* ``client``   — a customer brings a part back. On confirm the part is reintegrated
                 into stock (movement ``in``). An optional avoir is the existing
                 :class:`~app.modules.credit_note.models.CreditNote`.
* ``supplier`` — defective goods are sent back to a supplier. On confirm the part
                 leaves our stock (movement ``out``). An optional avoir is the
                 lightweight :class:`SupplierCreditNote` defined below.

Lifecycle::

    draft → confirmed   (assigns BR number, locks lines, applies stock movement)
    draft → cancelled   (no stock impact)
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


class BonDeRetourPartyType(str, enum.Enum):
    client = "client"
    supplier = "supplier"


class BonDeRetourStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"   # doc_number assigned, lines locked, stock moved
    cancelled = "cancelled"
    reversed = "reversed"     # confirmed BR whose stock movements have been undone


class BonDeRetourLineCondition(str, enum.Enum):
    neuf = "neuf"
    utilise = "utilise"
    endommage = "endommage"


class SupplierCreditNoteStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    void = "void"


class BonDeRetour(Base):
    __tablename__ = "bon_de_retour"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4())
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    party_type: Mapped[BonDeRetourPartyType] = mapped_column(
        String(20), nullable=False
    )
    # Exactly one of these is set, per party_type (enforced in the service layer).
    customer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="RESTRICT"), nullable=True
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=True
    )

    # Optional links to the originating document (for avoir creation / traceability).
    source_invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True
    )
    source_supplier_invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("supplier_invoice.id", ondelete="SET NULL"), nullable=True
    )

    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[BonDeRetourStatus] = mapped_column(
        String(20),
        nullable=False,
        default=BonDeRetourStatus.draft,
        server_default="draft",
    )

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Totals in minor currency units (cents)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    vat_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Avoir links. credit_note_id is a real FK (credit_note has no back-link, so no cycle).
    # supplier_credit_note_id is a plain reference column — a real FK here would form a
    # cycle with supplier_credit_note.bon_de_retour_id and break create_all on SQLite.
    credit_note_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("credit_note.id", ondelete="SET NULL"), nullable=True
    )
    supplier_credit_note_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

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

    lines: Mapped[list["BonDeRetourLine"]] = relationship(
        "BonDeRetourLine", back_populates="bon_de_retour", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        Index("ix_bdr_garage_id", "garage_id"),
        Index("ix_bdr_status", "status"),
        Index("ix_bdr_party_type", "party_type"),
        Index("ix_bdr_customer_id", "customer_id"),
        Index("ix_bdr_supplier_id", "supplier_id"),
        Index("ix_bdr_garage_status", "garage_id", "status"),
    )


class BonDeRetourLine(Base):
    __tablename__ = "bon_de_retour_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    bon_de_retour_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bon_de_retour.id", ondelete="CASCADE"), nullable=False
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

    # Physical condition recorded during the "contrôle état pièce" step.
    condition: Mapped[Optional[BonDeRetourLineCondition]] = mapped_column(String(20), nullable=True)
    # Client returns only: whether the returned item re-enters sellable stock on confirm.
    restock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    bon_de_retour: Mapped["BonDeRetour"] = relationship("BonDeRetour", back_populates="lines")

    __table_args__ = (
        Index("ix_bdr_line_bon_de_retour_id", "bon_de_retour_id"),
    )


class SupplierCreditNote(Base):
    """Avoir fournisseur — minimal financial document for a supplier return.

    Records the document and its amount/status only. Accounting-export integration
    (reverse purchases entry) is a deliberate follow-up, not part of this version.
    """

    __tablename__ = "supplier_credit_note"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4())
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("supplier_invoice.id", ondelete="SET NULL"), nullable=True
    )
    bon_de_retour_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("bon_de_retour.id", ondelete="SET NULL"), nullable=True
    )

    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[SupplierCreditNoteStatus] = mapped_column(
        String(20),
        nullable=False,
        default=SupplierCreditNoteStatus.draft,
        server_default="draft",
    )

    total_ht_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    total_ttc_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_exported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_scn_garage_id", "garage_id"),
        Index("ix_scn_supplier_id", "supplier_id"),
        Index("ix_scn_status", "status"),
        Index("ix_scn_bon_de_retour_id", "bon_de_retour_id"),
    )
