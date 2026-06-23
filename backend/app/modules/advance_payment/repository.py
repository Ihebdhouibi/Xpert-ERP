"""Advance payment repository — DB access layer."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.advance_payment.models import AdvancePayment


async def list_all_by_garage(
    db: AsyncSession,
    garage_id: int,
    *,
    status: Optional[str] = None,
) -> list[AdvancePayment]:
    """Return all advances for a garage, optionally filtered by status (pending/applied)."""
    q = select(AdvancePayment).where(AdvancePayment.garage_id == garage_id)
    if status == "pending":
        q = q.where(AdvancePayment.applied_to_invoice_id.is_(None))
    elif status == "applied":
        q = q.where(AdvancePayment.applied_to_invoice_id.is_not(None))
    q = q.order_by(AdvancePayment.id.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def create(db: AsyncSession, advance: AdvancePayment) -> None:
    db.add(advance)
    await db.flush()


async def get_by_id(
    db: AsyncSession, advance_id: int, garage_id: int
) -> Optional[AdvancePayment]:
    result = await db.execute(
        select(AdvancePayment).where(
            AdvancePayment.id == advance_id,
            AdvancePayment.garage_id == garage_id,
        )
    )
    return result.scalar_one_or_none()


async def list_by_customer(
    db: AsyncSession, customer_id: int, garage_id: int
) -> list[AdvancePayment]:
    result = await db.execute(
        select(AdvancePayment)
        .where(
            AdvancePayment.customer_id == customer_id,
            AdvancePayment.garage_id == garage_id,
        )
        .order_by(AdvancePayment.id)
    )
    return list(result.scalars().all())


async def list_by_invoice(
    db: AsyncSession, invoice_id: int, garage_id: int
) -> list[AdvancePayment]:
    """Return advances that were applied to a specific invoice."""
    result = await db.execute(
        select(AdvancePayment)
        .where(
            AdvancePayment.applied_to_invoice_id == invoice_id,
            AdvancePayment.garage_id == garage_id,
        )
        .order_by(AdvancePayment.id)
    )
    return list(result.scalars().all())


async def list_unapplied_by_customer(
    db: AsyncSession, customer_id: int, garage_id: int
) -> list[AdvancePayment]:
    """Return advances not yet applied to any invoice, oldest first."""
    result = await db.execute(
        select(AdvancePayment)
        .where(
            AdvancePayment.customer_id == customer_id,
            AdvancePayment.garage_id == garage_id,
            AdvancePayment.applied_to_invoice_id.is_(None),
        )
        .order_by(AdvancePayment.id)
    )
    return list(result.scalars().all())
