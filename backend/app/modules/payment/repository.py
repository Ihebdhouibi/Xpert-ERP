"""Payment repository — simple CRUD, no update/delete (payments are immutable)."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment.models import Payment


async def create(db: AsyncSession, payment: Payment) -> Payment:
    db.add(payment)
    await db.flush()
    return payment


async def get_by_id(
    db: AsyncSession, payment_id: int, garage_id: int
) -> Optional[Payment]:
    result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.garage_id == garage_id,
        )
    )
    return result.scalar_one_or_none()


async def list_by_invoice(
    db: AsyncSession, invoice_id: int, garage_id: int
) -> Sequence[Payment]:
    result = await db.execute(
        select(Payment)
        .where(Payment.invoice_id == invoice_id, Payment.garage_id == garage_id)
        .order_by(Payment.id)
    )
    return result.scalars().all()
