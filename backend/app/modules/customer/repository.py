"""Customer repository — all DB queries for the customer module.

Functions return ORM rows (or None / lists / tuples). Callers own the
transaction; writes flush but do not commit.
"""
from __future__ import annotations

import uuid as uuid_lib
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.customer.models import (
    Customer,
    CustomerBalanceEvent,
    CustomerContact,
    CustomerStatus,
    CustomerType,
)


# ---------------------------------------------------------------------------
# Get-by helpers
# ---------------------------------------------------------------------------


async def get_by_id(
    db: AsyncSession,
    garage_id: int,
    customer_id: int,
    *,
    include_deleted: bool = False,
    with_contacts: bool = False,
) -> Optional[Customer]:
    stmt = select(Customer).where(
        Customer.id == customer_id, Customer.garage_id == garage_id
    )
    if not include_deleted:
        stmt = stmt.where(Customer.deleted_at.is_(None))
    if with_contacts:
        stmt = stmt.options(selectinload(Customer.contacts))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_public_id(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    *,
    include_deleted: bool = False,
    with_contacts: bool = False,
) -> Optional[Customer]:
    try:
        uid = uuid_lib.UUID(public_id)
    except (ValueError, AttributeError):
        return None

    stmt = select(Customer).where(
        Customer.public_id == uid, Customer.garage_id == garage_id
    )
    if not include_deleted:
        stmt = stmt.where(Customer.deleted_at.is_(None))
    if with_contacts:
        stmt = stmt.options(selectinload(Customer.contacts))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Duplicate-detection lookups
#
# Each returns the first live (non-soft-deleted) match in the garage, or None.
# The service combines results to apply the M2 rule:
# `fiscal_id` + (`phone_e164` OR `email`) ⇒ merge prompt.
# ---------------------------------------------------------------------------


async def find_by_fiscal_id(
    db: AsyncSession, garage_id: int, fiscal_id: str
) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(
            Customer.garage_id == garage_id,
            Customer.fiscal_id == fiscal_id,
            Customer.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def find_by_phone(
    db: AsyncSession, garage_id: int, phone_e164: str
) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(
            Customer.garage_id == garage_id,
            Customer.phone_e164 == phone_e164,
            Customer.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def find_by_email(
    db: AsyncSession, garage_id: int, email: str
) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(
            Customer.garage_id == garage_id,
            Customer.email == email,
            Customer.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def find_by_name(
    db: AsyncSession,
    garage_id: int,
    full_name: str,
    company_name: Optional[str] = None,
) -> Optional[Customer]:
    """Return the first live customer with a case-insensitive matching name.

    Used as a last-resort duplicate check for bulk imports where a row carries
    neither a phone nor an email (the stronger identity keys). When
    `company_name` is supplied, both names must match.
    """
    stmt = select(Customer).where(
        Customer.garage_id == garage_id,
        func.lower(Customer.full_name) == full_name.lower(),
        Customer.deleted_at.is_(None),
    )
    if company_name is not None:
        stmt = stmt.where(func.lower(Customer.company_name) == company_name.lower())
    result = await db.execute(stmt)
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _build_search_filters(
    garage_id: int,
    *,
    q: Optional[str],
    status: Optional[CustomerStatus],
    segment: Optional[str],
    type_: Optional[CustomerType],
    include_deleted: bool,
) -> list:
    """Compose the WHERE clauses shared by search() and count_search()."""
    filters = [Customer.garage_id == garage_id]
    if not include_deleted:
        filters.append(Customer.deleted_at.is_(None))
    if status is not None:
        filters.append(Customer.status == status)
    if segment is not None:
        filters.append(Customer.segment == segment)
    if type_ is not None:
        filters.append(Customer.type == type_)

    if q:
        pattern = f"%{q.strip()}%"
        # ILIKE uses the GIN trigram index on PostgreSQL (gin_trgm_ops);
        # on SQLite it degrades to a table scan, which is fine for tests.
        filters.append(
            or_(
                Customer.full_name.ilike(pattern),
                func.coalesce(Customer.company_name, "").ilike(pattern),
                Customer.phone_e164.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.fiscal_id.ilike(pattern),
            )
        )
    return filters


async def search(
    db: AsyncSession,
    garage_id: int,
    *,
    q: Optional[str] = None,
    status: Optional[CustomerStatus] = None,
    segment: Optional[str] = None,
    type_: Optional[CustomerType] = None,
    include_deleted: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> list[Customer]:
    filters = _build_search_filters(
        garage_id,
        q=q,
        status=status,
        segment=segment,
        type_=type_,
        include_deleted=include_deleted,
    )
    stmt = (
        select(Customer)
        .where(*filters)
        # nulls_last is PG-only; portable alternative:
        .order_by(Customer.last_visit_at.is_(None), Customer.last_visit_at.desc(), Customer.full_name)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_search(
    db: AsyncSession,
    garage_id: int,
    *,
    q: Optional[str] = None,
    status: Optional[CustomerStatus] = None,
    segment: Optional[str] = None,
    type_: Optional[CustomerType] = None,
    include_deleted: bool = False,
) -> int:
    filters = _build_search_filters(
        garage_id,
        q=q,
        status=status,
        segment=segment,
        type_=type_,
        include_deleted=include_deleted,
    )
    result = await db.execute(
        select(func.count(Customer.id)).where(*filters)
    )
    return int(result.scalar_one())


# ---------------------------------------------------------------------------
# Balance ledger
# ---------------------------------------------------------------------------


async def list_balance_events(
    db: AsyncSession,
    customer_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[CustomerBalanceEvent]:
    result = await db.execute(
        select(CustomerBalanceEvent)
        .where(CustomerBalanceEvent.customer_id == customer_id)
        .order_by(CustomerBalanceEvent.occurred_at.desc(), CustomerBalanceEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_balance_events(db: AsyncSession, customer_id: int) -> int:
    result = await db.execute(
        select(func.count(CustomerBalanceEvent.id)).where(
            CustomerBalanceEvent.customer_id == customer_id
        )
    )
    return int(result.scalar_one())


# ---------------------------------------------------------------------------
# Contact helpers (used by the service when (re)building a customer's contacts)
# ---------------------------------------------------------------------------


async def delete_contacts_for_customer(
    db: AsyncSession, customer_id: int
) -> None:
    """Remove all contacts for a customer. Caller will re-add the new set."""
    result = await db.execute(
        select(CustomerContact).where(CustomerContact.customer_id == customer_id)
    )
    for contact in result.scalars().all():
        await db.delete(contact)
    await db.flush()


async def patch_from_ocr(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
    fields: dict[str, str],
) -> bool:
    """Apply confirmed OCR fields to a customer row.

    Returns True if the customer was found and updated, False otherwise.
    Only updates fields that are present and non-empty in *fields*.
    """
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.garage_id == garage_id,
            Customer.deleted_at.is_(None),
        )
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        return False

    # CIN number → fiscal_id
    numero_cin = fields.get("numero_cin", "").strip()
    if numero_cin:
        customer.fiscal_id = numero_cin

    # Build full_name from prenom + nom when both are available
    nom = fields.get("nom", "").strip()
    prenom = fields.get("prenom", "").strip()
    if prenom and nom:
        customer.full_name = f"{prenom} {nom}"
    elif nom:
        customer.full_name = nom

    await db.commit()
    return True
