"""Invoice repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.query_utils import apply_sort
from app.modules.customer.models import Customer
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


async def get_active_by_repair_order_id(
    db: AsyncSession, garage_id: int, repair_order_id: int
) -> Optional[Invoice]:
    """Return the active (non-cancelled) invoice linked to a repair order, if any."""
    stmt = select(Invoice).where(
        Invoice.garage_id == garage_id,
        Invoice.repair_order_id == repair_order_id,
        Invoice.status != InvoiceStatus.cancelled,
        Invoice.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_invoices(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    quotation_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "desc",
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

    needs_customer_join = bool(search) or sort_by == "customer_name"
    if needs_customer_join:
        base = base.outerjoin(Customer, Customer.id == Invoice.customer_id)
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            or_(
                Invoice.doc_number.ilike(pattern),
                Customer.full_name.ilike(pattern),
                func.coalesce(Customer.company_name, "").ilike(pattern),
            )
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    sortable_columns = {
        "doc_number": Invoice.doc_number,
        "total_minor": Invoice.total_minor,
        "outstanding_minor": Invoice.outstanding_minor,
        "due_at": Invoice.due_at,
        "status": Invoice.status,
    }
    if needs_customer_join:
        sortable_columns["customer_name"] = Customer.full_name
    base = apply_sort(base, sort_by, sort_dir, sortable_columns, default=Invoice.created_at)

    rows = await db.execute(
        base.options(selectinload(Invoice.lines))
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
