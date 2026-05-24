"""AdvancePayment ORM model — pre-invoice deposit linked to a customer."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK
from app.modules.payment.models import PaymentMethod  # reuse existing enum


class AdvancePayment(Base):
    __tablename__ = "advance_payment"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False
    )
    # Nullable: repair order may not exist yet when deposit is taken
    repair_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum"),
        nullable=False,
        default=PaymentMethod.cash,
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Set when this advance is applied to an issued invoice
    applied_to_invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # How much was actually applied (may be less than amount_minor if partially applied)
    applied_amount_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_advance_payment_garage_customer", "garage_id", "customer_id"),
        Index("ix_advance_payment_invoice", "applied_to_invoice_id"),
    )
