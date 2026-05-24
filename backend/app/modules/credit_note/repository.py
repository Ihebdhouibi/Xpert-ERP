"""Credit note and refund repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.credit_note.models import CreditNote, Refund


async def create_credit_note(db: AsyncSession, cn: CreditNote) -> CreditNote:
    db.add(cn)
    await db.flush()
    return cn


async def get_credit_note_by_id(
    db: AsyncSession, cn_id: int, garage_id: int
) -> Optional[CreditNote]:
    result = await db.execute(
        select(CreditNote)
        .where(CreditNote.id == cn_id, CreditNote.garage_id == garage_id)
        .options(selectinload(CreditNote.refunds))
    )
    return result.scalar_one_or_none()


async def list_credit_notes_by_invoice(
    db: AsyncSession, invoice_id: int, garage_id: int
) -> list[CreditNote]:
    result = await db.execute(
        select(CreditNote)
        .where(CreditNote.invoice_id == invoice_id, CreditNote.garage_id == garage_id)
        .order_by(CreditNote.id)
    )
    return list(result.scalars().all())


async def list_credit_notes(
    db: AsyncSession,
    garage_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[CreditNote], int]:
    base = select(CreditNote).where(CreditNote.garage_id == garage_id)
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total: int = total_result.scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(CreditNote.id.desc()).offset(offset).limit(page_size))
    return list(result.scalars().all()), total


async def save_credit_note(db: AsyncSession, cn: CreditNote) -> CreditNote:
    await db.flush()
    return cn


# ---------------------------------------------------------------------------
# Refund repository
# ---------------------------------------------------------------------------


async def create_refund(db: AsyncSession, refund: Refund) -> Refund:
    db.add(refund)
    await db.flush()
    return refund


async def get_refund_by_id(
    db: AsyncSession, refund_id: int, garage_id: int
) -> Optional[Refund]:
    result = await db.execute(
        select(Refund).where(Refund.id == refund_id, Refund.garage_id == garage_id)
    )
    return result.scalar_one_or_none()


async def list_refunds_by_payment(
    db: AsyncSession, payment_id: int, garage_id: int
) -> list[Refund]:
    result = await db.execute(
        select(Refund)
        .where(Refund.payment_id == payment_id, Refund.garage_id == garage_id)
        .order_by(Refund.id)
    )
    return list(result.scalars().all())


async def total_refunded_for_payment(
    db: AsyncSession, payment_id: int
) -> int:
    """Sum of all refunds already issued against a payment."""
    result = await db.execute(
        select(func.coalesce(func.sum(Refund.amount_minor), 0))
        .where(Refund.payment_id == payment_id)
    )
    return int(result.scalar_one())
