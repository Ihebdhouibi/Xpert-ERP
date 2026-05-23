"""Customer service — business logic for the customer module.

The service owns:

- Duplicate detection per the M2 merge rule:
  `fiscal_id` AND (`phone_e164` OR `email`) ⇒ merge prompt.
  A `fiscal_id`-only collision is also surfaced as a merge prompt rather than
  letting the DB partial-unique constraint return a 500.
- Optimistic locking on update via the `version` column.
- Soft delete and admin-only restore.
- Audit hooks on every create / update / delete / restore / credit-limit
  change / balance adjustment.
- Atomic balance-event posting (ledger row + customer.outstanding_minor in
  the same transaction).

Service functions flush via the audit writer but do NOT commit — the calling
endpoint owns the transaction (matches the auth/rbac modules).
"""
from __future__ import annotations

import enum
import uuid as uuid_lib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.audit.service import audit
from app.modules.customer import repository as repo
from app.modules.customer.models import (
    ContactChannel,
    Customer,
    CustomerBalanceEvent,
    CustomerContact,
    CustomerStatus,
    CustomerType,
)
from app.modules.customer.schemas import (
    CreditLimitUpdateRequest,
    CustomerBalanceEventCreateRequest,
    CustomerContactCreate,
    CustomerCreateRequest,
    CustomerUpdateRequest,
    MergeMatchReason,
)

logger = get_logger("customer")


# ---------------------------------------------------------------------------
# Exceptions surfaced to the router layer
# ---------------------------------------------------------------------------


class CustomerNotFoundError(Exception):
    """Customer does not exist in the actor's garage."""


class OptimisticLockError(Exception):
    """Submitted `version` does not match the current row."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"Stale version: client sent {expected}, current is {actual}"
        )
        self.expected = expected
        self.actual = actual


class FiscalIdConflictError(Exception):
    """A fiscal_id update would collide with another live customer."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateMatch:
    """Returned by `create_customer` when the merge rule fires.

    Reason values come from `schemas.MergeMatchReason`.
    """

    existing: Customer
    reason: str


CreateResult = Union[Customer, DuplicateMatch]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _to_audit_dict(obj: Customer) -> dict[str, Any]:
    """Serialize an ORM Customer row to a JSON-safe dict for audit storage."""
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if val is None:
            out[col.name] = None
        elif isinstance(val, datetime):
            out[col.name] = val.isoformat()
        elif isinstance(val, uuid_lib.UUID):
            out[col.name] = str(val)
        elif isinstance(val, enum.Enum):
            out[col.name] = val.value
        else:
            out[col.name] = val
    return out


def _apply_contacts(
    customer: Customer, contacts: list[CustomerContactCreate]
) -> None:
    """Replace the customer's contacts list with the supplied set."""
    customer.contacts.clear()
    for c in contacts:
        customer.contacts.append(
            CustomerContact(
                channel=c.channel,
                value=c.value,
                label=c.label,
                is_primary=c.is_primary,
            )
        )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


async def _check_duplicate(
    db: AsyncSession,
    garage_id: int,
    payload: CustomerCreateRequest,
) -> Optional[DuplicateMatch]:
    """Apply the M2 merge rule. Returns None if creation can proceed."""
    if not payload.fiscal_id:
        return None  # fiscal_id is the anchor for the merge rule

    existing = await repo.find_by_fiscal_id(db, garage_id, payload.fiscal_id)
    if existing is None:
        return None

    if payload.phone_e164 and existing.phone_e164 == payload.phone_e164:
        return DuplicateMatch(existing, MergeMatchReason.PHONE_AND_FISCAL_ID)
    if payload.email and existing.email and existing.email.lower() == payload.email.lower():
        return DuplicateMatch(existing, MergeMatchReason.EMAIL_AND_FISCAL_ID)

    # fiscal_id collision without contact match: DB partial-unique would
    # reject the INSERT with a generic constraint error; surface it cleanly.
    return DuplicateMatch(existing, MergeMatchReason.FISCAL_ID_ONLY)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def create_customer(
    db: AsyncSession,
    *,
    garage_id: int,
    actor_user_id: Optional[int],
    payload: CustomerCreateRequest,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> CreateResult:
    """Create a customer or signal a duplicate match.

    Returns a `Customer` on success (caller must commit) or a `DuplicateMatch`
    that the router translates into a 409 merge-prompt response.
    """
    duplicate = await _check_duplicate(db, garage_id, payload)
    if duplicate is not None:
        return duplicate

    new_customer = Customer(
        garage_id=garage_id,
        type=payload.type,
        full_name=payload.full_name,
        company_name=payload.company_name,
        fiscal_id=payload.fiscal_id,
        email=payload.email,
        phone_e164=payload.phone_e164,
        address=payload.address.model_dump(exclude_none=True) if payload.address else None,
        segment=payload.segment,
        credit_limit_minor=payload.credit_limit_minor,
        credit_currency=payload.credit_currency,
        notes=payload.notes,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    _apply_contacts(new_customer, payload.contacts)

    db.add(new_customer)
    await db.flush()  # populate id / public_id

    await audit(
        db=db,
        garage_id=garage_id,
        user_id=actor_user_id,
        component="customer",
        action="create",
        entity_type="customer",
        entity_id=new_customer.id,
        new_value=_to_audit_dict(new_customer),
        request_id=request_id,
        ip_address=ip_address,
    )
    return new_customer


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

# Fields the general PATCH endpoint may change. credit_limit_minor and
# credit_currency are excluded — they use a dedicated endpoint with audit
# reason and their own permission.
_UPDATABLE_FIELDS = (
    "full_name",
    "company_name",
    "fiscal_id",
    "email",
    "phone_e164",
    "segment",
    "status",
    "notes",
)


async def update_customer(
    db: AsyncSession,
    *,
    garage_id: int,
    actor_user_id: Optional[int],
    public_id: str,
    payload: CustomerUpdateRequest,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Customer:
    """Apply a partial update with optimistic locking and audit.

    Raises:
        CustomerNotFoundError: when the row does not exist in this garage.
        OptimisticLockError: when `payload.version` is stale.
        FiscalIdConflictError: when the new fiscal_id is taken by another live
            customer in the same garage.
    """
    target = await repo.get_by_public_id(
        db, garage_id, public_id, with_contacts=True
    )
    if target is None:
        raise CustomerNotFoundError(public_id)

    if target.version != payload.version:
        raise OptimisticLockError(expected=payload.version, actual=target.version)

    if payload.fiscal_id is not None and payload.fiscal_id != target.fiscal_id:
        clash = await repo.find_by_fiscal_id(db, garage_id, payload.fiscal_id)
        if clash is not None and clash.id != target.id:
            raise FiscalIdConflictError(payload.fiscal_id)

    old_snapshot = _to_audit_dict(target)
    changed: dict[str, Any] = {}

    for field in _UPDATABLE_FIELDS:
        if field not in payload.model_fields_set:
            continue
        new_val = getattr(payload, field)
        if getattr(target, field) != new_val:
            setattr(target, field, new_val)
            changed[field] = new_val

    if "address" in payload.model_fields_set:
        new_addr = (
            payload.address.model_dump(exclude_none=True)
            if payload.address
            else None
        )
        if target.address != new_addr:
            target.address = new_addr
            changed["address"] = new_addr

    if not changed:
        # No-op update — still return the row but skip version bump and audit.
        return target

    target.version += 1
    target.updated_by_user_id = actor_user_id

    await audit(
        db=db,
        garage_id=garage_id,
        user_id=actor_user_id,
        component="customer",
        action="update",
        entity_type="customer",
        entity_id=target.id,
        old_value=old_snapshot,
        new_value=_to_audit_dict(target),
        request_id=request_id,
        ip_address=ip_address,
    )
    return target


# ---------------------------------------------------------------------------
# Soft delete / restore
# ---------------------------------------------------------------------------


async def soft_delete_customer(
    db: AsyncSession,
    *,
    garage_id: int,
    actor_user_id: Optional[int],
    public_id: str,
    reason: Optional[str] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Customer:
    # include_deleted so the idempotent re-delete path can short-circuit.
    target = await repo.get_by_public_id(
        db, garage_id, public_id, include_deleted=True
    )
    if target is None:
        raise CustomerNotFoundError(public_id)
    if target.deleted_at is not None:
        return target  # already deleted, idempotent

    old_snapshot = _to_audit_dict(target)
    target.deleted_at = _utcnow()
    target.status = CustomerStatus.inactive
    target.updated_by_user_id = actor_user_id

    await audit(
        db=db,
        garage_id=garage_id,
        user_id=actor_user_id,
        component="customer",
        action="delete",
        entity_type="customer",
        entity_id=target.id,
        old_value=old_snapshot,
        new_value=_to_audit_dict(target),
        reason=reason,
        request_id=request_id,
        ip_address=ip_address,
    )
    return target


async def restore_customer(
    db: AsyncSession,
    *,
    garage_id: int,
    actor_user_id: Optional[int],
    public_id: str,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Customer:
    """Admin-only restore. Caller must enforce the role check.

    Re-checks fiscal_id uniqueness against live rows before restoring, since
    the partial unique index only constrains live rows.
    """
    target = await repo.get_by_public_id(
        db, garage_id, public_id, include_deleted=True
    )
    if target is None:
        raise CustomerNotFoundError(public_id)
    if target.deleted_at is None:
        return target  # already live, idempotent

    if target.fiscal_id:
        clash = await repo.find_by_fiscal_id(db, garage_id, target.fiscal_id)
        if clash is not None and clash.id != target.id:
            raise FiscalIdConflictError(target.fiscal_id)

    old_snapshot = _to_audit_dict(target)
    target.deleted_at = None
    target.status = CustomerStatus.active
    target.updated_by_user_id = actor_user_id

    await audit(
        db=db,
        garage_id=garage_id,
        user_id=actor_user_id,
        component="customer",
        action="restore",
        entity_type="customer",
        entity_id=target.id,
        old_value=old_snapshot,
        new_value=_to_audit_dict(target),
        request_id=request_id,
        ip_address=ip_address,
    )
    return target


# ---------------------------------------------------------------------------
# Credit limit
# ---------------------------------------------------------------------------


async def update_credit_limit(
    db: AsyncSession,
    *,
    garage_id: int,
    actor_user_id: Optional[int],
    public_id: str,
    payload: CreditLimitUpdateRequest,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Customer:
    target = await repo.get_by_public_id(db, garage_id, public_id)
    if target is None:
        raise CustomerNotFoundError(public_id)

    old_snapshot = _to_audit_dict(target)
    target.credit_limit_minor = payload.credit_limit_minor
    target.credit_currency = payload.credit_currency
    target.version += 1
    target.updated_by_user_id = actor_user_id

    await audit(
        db=db,
        garage_id=garage_id,
        user_id=actor_user_id,
        component="customer",
        action="credit_limit.update",
        entity_type="customer",
        entity_id=target.id,
        old_value=old_snapshot,
        new_value=_to_audit_dict(target),
        reason=payload.reason,
        request_id=request_id,
        ip_address=ip_address,
    )
    return target


# ---------------------------------------------------------------------------
# Balance ledger
# ---------------------------------------------------------------------------


async def add_balance_event(
    db: AsyncSession,
    *,
    garage_id: int,
    actor_user_id: Optional[int],
    public_id: str,
    payload: CustomerBalanceEventCreateRequest,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> CustomerBalanceEvent:
    """Post a manual ledger event and update the customer's outstanding balance.

    Row-locks the customer to keep the ledger and outstanding column
    consistent under concurrent posts.
    """
    # SELECT ... FOR UPDATE to serialize concurrent balance adjustments.
    result = await db.execute(
        select(Customer)
        .where(
            Customer.garage_id == garage_id,
            Customer.deleted_at.is_(None),
        )
        .where(Customer.public_id == uuid_lib.UUID(public_id))
        .with_for_update()
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise CustomerNotFoundError(public_id)

    event = CustomerBalanceEvent(
        customer_id=target.id,
        reason=payload.reason,
        delta_minor=payload.delta_minor,
        currency=payload.currency,
        created_by_user_id=actor_user_id,
    )
    db.add(event)

    target.outstanding_minor = target.outstanding_minor + payload.delta_minor
    target.updated_by_user_id = actor_user_id

    await db.flush()  # populate event.id

    await audit(
        db=db,
        garage_id=garage_id,
        user_id=actor_user_id,
        component="customer",
        action="balance.adjust",
        entity_type="customer_balance_event",
        entity_id=event.id,
        new_value={
            "customer_id": target.id,
            "reason": event.reason,
            "delta_minor": event.delta_minor,
            "currency": event.currency,
            "new_outstanding_minor": target.outstanding_minor,
        },
        reason=payload.note,
        request_id=request_id,
        ip_address=ip_address,
    )
    return event
