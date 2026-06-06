"""Invoice repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.invoice.models import Invoice, InvoiceLine, InvoiceStatus


async def create(db: AsyncSession, invoice: Invoice) -> Invoice:
    db.add(invoice)
    await db.flush()
    return invoice


async def get_by_id(
    db: AsyncSession,
    invoice_id: int,
    garage_id: int,
    include_deleted: bool = False,
) -> Optional[Invoice]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id, Invoice.garage_id == garage_id)
    )
    if not include_deleted:
        stmt = stmt.where(Invoice.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_public_id(
    db: AsyncSession,
    public_id: str,
    garage_id: int,
    include_deleted: bool = False,
) -> Optional[Invoice]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.public_id == public_id, Invoice.garage_id == garage_id)
    )
    if not include_deleted:
        stmt = stmt.where(Invoice.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_invoices(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    quotation_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Invoice], int]:
    base = (
        select(Invoice)
        .where(Invoice.garage_id == garage_id, Invoice.deleted_at.is_(None))
    )
    if customer_id is not None:
        base = base.where(Invoice.customer_id == customer_id)
    if status is not None:
        base = base.where(Invoice.status == status)
    if quotation_id is not None:
        base = base.where(Invoice.quotation_id == quotation_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = await db.execute(
        base.options(selectinload(Invoice.lines))
        .order_by(Invoice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def save(db: AsyncSession, invoice: Invoice) -> Invoice:
    await db.flush()
    return invoice


async def soft_delete(db: AsyncSession, invoice: Invoice, deleted_by: int) -> None:
    from datetime import datetime, timezone
    invoice.deleted_at = datetime.now(tz=timezone.utc)
    invoice.updated_by = deleted_by
    await db.flush()


async def add_line(db: AsyncSession, line: InvoiceLine) -> InvoiceLine:
    db.add(line)
    await db.flush()
    return line


async def get_line(db: AsyncSession, line_id: int, invoice_id: int) -> Optional[InvoiceLine]:
    result = await db.execute(
        select(InvoiceLine).where(
            InvoiceLine.id == line_id,
            InvoiceLine.invoice_id == invoice_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_line(db: AsyncSession, line: InvoiceLine) -> None:
    await db.delete(line)
    await db.flush()
