"""Credit note and refund ORM models."""
from __future__ import annotations

import enum
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
from app.modules.payment.models import PaymentMethod


class CreditNoteStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    void = "void"


class CreditNote(Base):
    """Avoir / credit note — issued to document a credit owed to a customer.

    Typically auto-created when a paid or partial invoice is cancelled,
    or manually created against any issued invoice.
    """

    __tablename__ = "credit_note"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoice.id", ondelete="RESTRICT"), nullable=False
    )

    doc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[CreditNoteStatus] = mapped_column(
        Enum(CreditNoteStatus, name="credit_note_status_enum"),
        nullable=False,
        default=CreditNoteStatus.draft,
        server_default="draft",
    )

    # Amount credited (always positive; represents money owed back to customer)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="credit_notes")  # type: ignore[name-defined]
    refunds: Mapped[list["Refund"]] = relationship("Refund", back_populates="credit_note")

    __table_args__ = (
        Index("ix_credit_note_garage_id", "garage_id"),
        Index("ix_credit_note_invoice_id", "invoice_id"),
        Index("ix_credit_note_status", "status"),
    )


class Refund(Base):
    """Refund — records the actual return of money to a customer.

    Linked to the original Payment being refunded and optionally
    to the CreditNote that authorised the refund.
    """

    __tablename__ = "refund"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Original payment that is being (partially or fully) refunded
    payment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment.id", ondelete="RESTRICT"), nullable=False
    )

    # Credit note that authorises / documents this refund (optional)
    credit_note_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("credit_note.id", ondelete="SET NULL"), nullable=True
    )

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Refund method (usually matches original payment method)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum"),
        nullable=False,
        default=PaymentMethod.cash,
    )

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    refunded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Cash session open at the time the refund was paid out (nullable — no session required)
    cash_session_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("cash_session.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="refunds")  # type: ignore[name-defined]
    credit_note: Mapped[Optional["CreditNote"]] = relationship("CreditNote", back_populates="refunds")

    __table_args__ = (
        Index("ix_refund_garage_id", "garage_id"),
        Index("ix_refund_payment_id", "payment_id"),
        Index("ix_refund_credit_note_id", "credit_note_id"),
    )
