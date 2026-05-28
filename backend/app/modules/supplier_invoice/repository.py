from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.supplier_invoice.models import SupplierInvoice, SupplierInvoiceStatus


class SupplierInvoiceRepository:
    @staticmethod
    async def get_by_public_id(
        db: AsyncSession,
        garage_id: int,
        public_id_str: str,
        include_deleted: bool = False,
    ) -> Optional[SupplierInvoice]:
        try:
            uid = uuid_lib.UUID(public_id_str)
        except ValueError:
            return None
        q = select(SupplierInvoice).where(
            SupplierInvoice.public_id == uid,
            SupplierInvoice.garage_id == garage_id,
        )
        if not include_deleted:
            q = q.where(SupplierInvoice.deleted_at.is_(None))
        result = await db.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        status: Optional[SupplierInvoiceStatus] = None,
        supplier_id: Optional[int] = None,
        po_id: Optional[int] = None,
        search: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SupplierInvoice], int]:
        base = select(SupplierInvoice).where(SupplierInvoice.garage_id == garage_id)
        if not include_deleted:
            base = base.where(SupplierInvoice.deleted_at.is_(None))
        if status is not None:
            base = base.where(SupplierInvoice.status == status.value)
        if supplier_id is not None:
            base = base.where(SupplierInvoice.supplier_id == supplier_id)
        if po_id is not None:
            base = base.where(SupplierInvoice.purchase_order_id == po_id)
        if search:
            base = base.where(SupplierInvoice.number.ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_q)).scalar_one()

        items_q = (
            base.order_by(SupplierInvoice.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await db.execute(items_q)
        return list(rows.scalars().all()), total

    @staticmethod
    async def create(
        db: AsyncSession,
        garage_id: int,
        supplier_id: int,
        purchase_order_id: int,
        number: str,
        lines: list[dict[str, Any]],
        total_ht: int,
        total_ttc: int,
        received_at: Optional[datetime],
        due_date: Optional[object],
        notes: Optional[str],
        created_by: Optional[int],
    ) -> SupplierInvoice:
        si = SupplierInvoice(
            garage_id=garage_id,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            number=number,
            lines=lines,
            total_ht=total_ht,
            total_ttc=total_ttc,
            received_at=received_at,
            due_date=due_date,
            notes=notes,
            created_by=created_by,
        )
        db.add(si)
        await db.flush()
        return si

    @staticmethod
    async def update(
        db: AsyncSession,
        si: SupplierInvoice,
        **kwargs: object,
    ) -> SupplierInvoice:
        for key, value in kwargs.items():
            setattr(si, key, value)
        si.version += 1
        si.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return si

    @staticmethod
    async def soft_delete(db: AsyncSession, si: SupplierInvoice) -> SupplierInvoice:
        si.deleted_at = datetime.now(timezone.utc)
        si.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return si
