from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    partially_received = "partially_received"
    completed = "completed"
    cancelled = "cancelled"


class POMatchFlag(str, enum.Enum):
    ok = "ok"
    qty_mismatch = "qty_mismatch"
    inv_mismatch = "inv_mismatch"


class PurchaseOrder(Base):
    __tablename__ = "purchase_order"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False
    )
    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        String(30), nullable=False, default=PurchaseOrderStatus.draft
    )
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_ht: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
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

    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        "PurchaseOrderLine",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.id",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_po_public_id"),
        Index("ix_po_garage_id", "garage_id"),
        Index("ix_po_garage_status", "garage_id", "status"),
        Index("ix_po_supplier_id", "supplier_id"),
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: an "Autre" line is for a part not (yet) in the catalogue. Its
    # free-text name is held in ``label``; once the client validates the BL, the
    # line is reassigned to a real part (part_id set).
    part_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="RESTRICT"), nullable=True
    )
    # Free-text designation for an "Autre" (uncatalogued) line.
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_ht: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_invoiced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_flag: Mapped[str] = mapped_column(
        String(30), nullable=False, default=POMatchFlag.ok.value
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder", back_populates="lines"
    )

    __table_args__ = (
        Index("ix_pol_po_id", "purchase_order_id"),
        Index("ix_pol_part_id", "part_id"),
    )
