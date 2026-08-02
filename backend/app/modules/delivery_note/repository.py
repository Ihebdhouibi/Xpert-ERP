"""Delivery Note repository — all DB queries."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.query_utils import apply_sort
from app.modules.customer.models import Customer
from app.modules.delivery_note.models import DeliveryNote, DeliveryNoteLine, DeliveryNoteStatus


async def create(db: AsyncSession, dn: DeliveryNote) -> DeliveryNote:
    db.add(dn)
    await db.flush()
    await db.refresh(dn)
    return dn


async def get_by_id(
    db: AsyncSession, dn_id: int, garage_id: int
) -> Optional[DeliveryNote]:
    result = await db.execute(
        select(DeliveryNote)
        .where(
            DeliveryNote.id == dn_id,
            DeliveryNote.garage_id == garage_id,
            DeliveryNote.deleted_at.is_(None),
        )
        .options(selectinload(DeliveryNote.lines))
    )
    return result.scalar_one_or_none()


async def get_by_public_id(
    db: AsyncSession, public_id: str, garage_id: int
) -> Optional[DeliveryNote]:
    result = await db.execute(
        select(DeliveryNote)
        .where(
            DeliveryNote.public_id == public_id,
            DeliveryNote.garage_id == garage_id,
            DeliveryNote.deleted_at.is_(None),
        )
        .options(selectinload(DeliveryNote.lines))
    )
    return result.scalar_one_or_none()


async def get_active_by_repair_order_id(
    db: AsyncSession, garage_id: int, repair_order_id: int
) -> Optional[DeliveryNote]:
    """Return the active (non-cancelled) delivery note linked to a repair order, if any."""
    result = await db.execute(
        select(DeliveryNote).where(
            DeliveryNote.garage_id == garage_id,
            DeliveryNote.repair_order_id == repair_order_id,
            DeliveryNote.status != DeliveryNoteStatus.cancelled,
            DeliveryNote.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def list_delivery_notes(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[DeliveryNoteStatus] = None,
    available_for_invoice: bool = False,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[DeliveryNote], int]:
    base = (
        select(DeliveryNote)
        .where(DeliveryNote.garage_id == garage_id, DeliveryNote.deleted_at.is_(None))
    )
    if customer_id is not None:
        base = base.where(DeliveryNote.customer_id == customer_id)
    if status is not None:
        base = base.where(DeliveryNote.status == status)
    if available_for_invoice:
        base = base.where(
            DeliveryNote.status.in_([DeliveryNoteStatus.issued, DeliveryNoteStatus.delivered]),
            DeliveryNote.invoice_id.is_(None),
        )
    if date_from is not None:
        base = base.where(DeliveryNote.created_at >= date_from)
    if date_to is not None:
        base = base.where(DeliveryNote.created_at <= date_to)

    needs_customer_join = bool(search) or sort_by == "customer_name"
    if needs_customer_join:
        base = base.outerjoin(Customer, Customer.id == DeliveryNote.customer_id)
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            or_(
                DeliveryNote.doc_number.ilike(pattern),
                Customer.full_name.ilike(pattern),
                func.coalesce(Customer.company_name, "").ilike(pattern),
            )
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    sortable_columns = {
        "doc_number": DeliveryNote.doc_number,
        "total_minor": DeliveryNote.total_minor,
        "status": DeliveryNote.status,
        "created_at": DeliveryNote.created_at,
    }
    if needs_customer_join:
        sortable_columns["customer_name"] = Customer.full_name
    base = apply_sort(base, sort_by, sort_dir, sortable_columns, default=DeliveryNote.created_at)

    rows = await db.execute(
        base.options(selectinload(DeliveryNote.lines))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def save(db: AsyncSession, dn: DeliveryNote) -> DeliveryNote:
    await db.flush()
    return dn


async def soft_delete(db: AsyncSession, dn: DeliveryNote, deleted_by: int) -> None:
    from datetime import datetime, timezone
    dn.deleted_at = datetime.now(tz=timezone.utc)
    dn.updated_by = deleted_by
    await db.flush()


async def add_line(db: AsyncSession, line: DeliveryNoteLine) -> DeliveryNoteLine:
    db.add(line)
    await db.flush()
    return line


async def get_line(
    db: AsyncSession, line_id: int, delivery_note_id: int
) -> Optional[DeliveryNoteLine]:
    result = await db.execute(
        select(DeliveryNoteLine).where(
            DeliveryNoteLine.id == line_id,
            DeliveryNoteLine.delivery_note_id == delivery_note_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_line(db: AsyncSession, line: DeliveryNoteLine) -> None:
    await db.delete(line)
    await db.flush()
