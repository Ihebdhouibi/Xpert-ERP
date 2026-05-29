"""Payment ORM model."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    card = "card"
    bank_transfer = "bank_transfer"
    cheque = "cheque"
    other = "other"


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

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
    is_exported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Linked to the cash session open at the time of payment (nullable — no session required)
    cash_session_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("cash_session.id", ondelete="SET NULL"), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")  # type: ignore[name-defined]
    cash_session: Mapped[Optional["CashSession"]] = relationship("CashSession", back_populates="payments")  # type: ignore[name-defined]
    refunds: Mapped[list["Refund"]] = relationship(  # type: ignore[name-defined]
        "Refund",
        back_populates="payment",
    )

    __table_args__ = (
        Index("ix_payment_invoice_id", "invoice_id"),
        Index("ix_payment_garage_id", "garage_id"),
    )
