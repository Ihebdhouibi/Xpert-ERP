"""Quotation repository — raw DB access."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.quotation.models import Quotation, QuotationLine, QuotationStatus


async def create(db: AsyncSession, quotation: Quotation) -> Quotation:
    db.add(quotation)
    await db.flush()
    await db.refresh(quotation, attribute_names=["lines"])
    return quotation


async def get_by_id(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    include_deleted: bool = False,
) -> Optional[Quotation]:
    stmt = (
        select(Quotation)
        .options(selectinload(Quotation.lines))
        .where(Quotation.id == quotation_id, Quotation.garage_id == garage_id)
    )
    if not include_deleted:
        stmt = stmt.where(Quotation.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_public_id(
    db: AsyncSession,
    public_id: str,
    garage_id: int,
    include_deleted: bool = False,
) -> Optional[Quotation]:
    stmt = (
        select(Quotation)
        .options(selectinload(Quotation.lines))
        .where(Quotation.public_id == public_id, Quotation.garage_id == garage_id)
    )
    if not include_deleted:
        stmt = stmt.where(Quotation.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_quotations(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[QuotationStatus] = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Quotation], int]:
    base_stmt = (
        select(Quotation)
        .where(Quotation.garage_id == garage_id, Quotation.deleted_at.is_(None))
    )
    if customer_id is not None:
        base_stmt = base_stmt.where(Quotation.customer_id == customer_id)
    if status is not None:
        base_stmt = base_stmt.where(Quotation.status == status)

    count_result = await db.execute(select(func.count()).select_from(base_stmt.subquery()))
    total = count_result.scalar_one()

    rows = await db.execute(
        base_stmt.options(selectinload(Quotation.lines))
        .order_by(Quotation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def save(db: AsyncSession, quotation: Quotation) -> Quotation:
    await db.flush()
    return quotation


async def soft_delete(db: AsyncSession, quotation: Quotation, deleted_by: int) -> None:
    from datetime import datetime, timezone
    quotation.deleted_at = datetime.now(tz=timezone.utc)
    quotation.updated_by = deleted_by
    await db.flush()


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------

async def add_line(db: AsyncSession, line: QuotationLine) -> QuotationLine:
    db.add(line)
    await db.flush()
    return line


async def get_line(db: AsyncSession, line_id: int, quotation_id: int) -> Optional[QuotationLine]:
    result = await db.execute(
        select(QuotationLine).where(
            QuotationLine.id == line_id,
            QuotationLine.quotation_id == quotation_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_line(db: AsyncSession, line: QuotationLine) -> None:
    await db.delete(line)
    await db.flush()
