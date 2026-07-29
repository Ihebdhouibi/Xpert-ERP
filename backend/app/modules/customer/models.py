from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
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
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK, CIText, JsonB


class CustomerType(str, enum.Enum):
    individual = "individual"
    company = "company"


class CustomerStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class ContactChannel(str, enum.Enum):
    phone = "phone"
    email = "email"
    whatsapp = "whatsapp"


class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType, name="customer_type_enum"), nullable=False
    )

    # Names: full_name is always populated (display name); company_name only for companies.
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    fiscal_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(CIText, nullable=True)
    phone_e164: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    address: Mapped[Optional[dict]] = mapped_column(JsonB, nullable=True)  # type: ignore[type-arg]

    segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus, name="customer_status_enum"),
        nullable=False,
        default=CustomerStatus.active,
        server_default="active",
    )

    # Money is stored as integer minor units (e.g. cents) to avoid float drift.
    credit_limit_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    credit_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # Derived snapshot: sum of customer_balance_event.delta_minor.
    # Kept on the row for fast list views; service must update it on ledger writes.
    outstanding_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )

    loyalty_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Tracks which credit threshold (80 or 90) was last notified to avoid spam.
    last_notified_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    last_visit_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    contacts: Mapped[list[CustomerContact]] = relationship(
        "CustomerContact",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    balance_events: Mapped[list[CustomerBalanceEvent]] = relationship(
        "CustomerBalanceEvent",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "type <> 'company' OR company_name IS NOT NULL",
            name="ck_customer_company_has_name",
        ),
        Index("ix_customer_garage_status", "garage_id", "status"),
        Index("ix_customer_garage_phone", "garage_id", "phone_e164"),
        Index("ix_customer_garage_email", "garage_id", "email"),
        # The unique fiscal_id constraint and trigram name index are partial /
        # GIN and live in the migration as raw SQL (Alembic cannot express them
        # via Column-level metadata).
    )


class CustomerContact(Base):
    __tablename__ = "customer_contact"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )

    channel: Mapped[ContactChannel] = mapped_column(
        Enum(ContactChannel, name="customer_contact_channel_enum"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="contacts")

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "channel", "value", name="uq_customer_contact_unique"
        ),
    )


class CustomerBalanceEvent(Base):
    """Append-only ledger of balance changes.

    Rows are never updated or deleted; corrections are posted as new events.
    The `reason` field is free-text (not an enum) so future modules
    (invoice, payment, credit_note) can post their own reasons without a
    migration.
    """

    __tablename__ = "customer_balance_event"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )

    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    delta_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    ref_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="balance_events")

    __table_args__ = (
        Index("ix_customer_balance_event_customer_occurred", "customer_id", "occurred_at"),
    )


class OverrideStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CreditOverrideRequest(Base):
    """One override request per (customer, doc_type) attempt.

    When a user tries to issue a document for a customer over their credit limit,
    a request is created here. An admin then approves or rejects it.
    Approval grants a time-limited window (expires_at) during which the user
    may issue one document of doc_type for that customer.
    """

    __tablename__ = "credit_override_request"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "invoice" | "delivery_note"
    source_document_public_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    status: Mapped[OverrideStatus] = mapped_column(
        Enum(OverrideStatus, name="override_status_enum"),
        nullable=False,
        default=OverrideStatus.pending,
        server_default="pending",
    )

    approved_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer: Mapped[Customer] = relationship("Customer")

    __table_args__ = (
        Index("ix_credit_override_garage_customer", "garage_id", "customer_id"),
        Index("ix_credit_override_garage_status", "garage_id", "status"),
    )


class CreditLimitRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CreditLimitChangeRequest(Base):
    """A staff-submitted request to change an existing customer's credit limit.

    Unlike `CreditOverrideRequest` (a one-time, time-limited window to issue a
    single document), approving this request permanently changes
    `Customer.credit_limit_minor`. Used by staff who hold `customer.update`
    but not `customer.credit_limit.update` (e.g. receptionist) — an admin must
    approve before the new limit takes effect.
    """

    __tablename__ = "credit_limit_change_request"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )

    current_credit_limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_credit_limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_credit_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[CreditLimitRequestStatus] = mapped_column(
        Enum(CreditLimitRequestStatus, name="credit_limit_request_status_enum"),
        nullable=False,
        default=CreditLimitRequestStatus.pending,
        server_default="pending",
    )

    approved_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer: Mapped[Customer] = relationship("Customer")

    __table_args__ = (
        Index("ix_credit_limit_request_garage_customer", "garage_id", "customer_id"),
        Index("ix_credit_limit_request_garage_status", "garage_id", "status"),
    )
