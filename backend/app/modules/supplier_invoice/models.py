from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK, JsonB


class SupplierInvoiceStatus(str, enum.Enum):
    draft = "draft"
    posted = "posted"        # three-way match run
    approved = "approved"    # approved for payment
    paid = "paid"
    cancelled = "cancelled"


class SIMatchStatus(str, enum.Enum):
    ok = "ok"
    qty_mismatch = "qty_mismatch"
    price_mismatch = "price_mismatch"


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoice"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id", ondelete="RESTRICT"), nullable=False
    )
    number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SupplierInvoiceStatus] = mapped_column(
        String(30), nullable=False, default=SupplierInvoiceStatus.draft
    )
    # Each element: {po_line_id, description, quantity, unit_price_ht, vat_rate,
    #                line_total_ht, line_total_ttc,
    #                match_status, po_quantity_ordered, po_quantity_received, po_unit_price_ht}
    lines: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonB, nullable=False, default=list
    )
    total_ht: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_ttc: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_discrepancy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
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

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_si_public_id"),
        Index("ix_si_garage_id", "garage_id"),
        Index("ix_si_garage_status", "garage_id", "status"),
        Index("ix_si_supplier_id", "supplier_id"),
        Index("ix_si_po_id", "purchase_order_id"),
    )
