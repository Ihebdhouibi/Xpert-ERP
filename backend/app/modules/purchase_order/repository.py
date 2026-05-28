from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchase_order.models import (
    POMatchFlag,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)


class PurchaseOrderRepository:
    @staticmethod
    async def get_by_public_id(
        db: AsyncSession,
        garage_id: int,
        public_id_str: str,
        include_deleted: bool = False,
    ) -> Optional[PurchaseOrder]:
        try:
            uid = uuid_lib.UUID(public_id_str)
        except ValueError:
            return None
        q = select(PurchaseOrder).where(
            PurchaseOrder.public_id == uid,
            PurchaseOrder.garage_id == garage_id,
        )
        if not include_deleted:
            q = q.where(PurchaseOrder.deleted_at.is_(None))
        result = await db.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        status: Optional[PurchaseOrderStatus] = None,
        supplier_id: Optional[int] = None,
        search: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PurchaseOrder], int]:
        base = select(PurchaseOrder).where(PurchaseOrder.garage_id == garage_id)
        if not include_deleted:
            base = base.where(PurchaseOrder.deleted_at.is_(None))
        if status is not None:
            base = base.where(PurchaseOrder.status == status.value)
        if supplier_id is not None:
            base = base.where(PurchaseOrder.supplier_id == supplier_id)
        if search:
            base = base.where(PurchaseOrder.doc_number.ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_q)).scalar_one()

        items_q = (
            base.order_by(PurchaseOrder.created_at.desc())
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
        doc_number: Optional[str],
        expected_delivery_date: Optional[object],
        notes: Optional[str],
        total_ht: int,
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            garage_id=garage_id,
            supplier_id=supplier_id,
            doc_number=doc_number,
            status=PurchaseOrderStatus.draft,
            expected_delivery_date=expected_delivery_date,
            notes=notes,
            total_ht=total_ht,
        )
        db.add(po)
        await db.flush()
        return po

    @staticmethod
    async def update(
        db: AsyncSession,
        po: PurchaseOrder,
        **kwargs: object,
    ) -> PurchaseOrder:
        for key, value in kwargs.items():
            setattr(po, key, value)
        po.version += 1
        po.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return po

    @staticmethod
    async def soft_delete(db: AsyncSession, po: PurchaseOrder) -> PurchaseOrder:
        po.deleted_at = datetime.now(timezone.utc)
        po.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return po


class PurchaseOrderLineRepository:
    @staticmethod
    async def get_by_id(
        db: AsyncSession, line_id: int, po_id: int
    ) -> Optional[PurchaseOrderLine]:
        result = await db.execute(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.id == line_id,
                PurchaseOrderLine.purchase_order_id == po_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        po_id: int,
        part_id: int,
        quantity_ordered: int,
        unit_price_ht: int,
    ) -> PurchaseOrderLine:
        line = PurchaseOrderLine(
            purchase_order_id=po_id,
            part_id=part_id,
            quantity_ordered=quantity_ordered,
            unit_price_ht=unit_price_ht,
        )
        db.add(line)
        await db.flush()
        return line

    @staticmethod
    async def delete_all_for_po(db: AsyncSession, po_id: int) -> None:
        from sqlalchemy import delete as sa_delete
        await db.execute(
            sa_delete(PurchaseOrderLine).where(
                PurchaseOrderLine.purchase_order_id == po_id
            )
        )

    @staticmethod
    def compute_match_flag(
        quantity_ordered: int,
        quantity_received: int,
        quantity_invoiced: int,
        tolerance_pct: float,
    ) -> str:
        if quantity_ordered == 0:
            return POMatchFlag.ok.value
        qty_diff_pct = abs(quantity_ordered - quantity_received) / quantity_ordered * 100
        if qty_diff_pct > tolerance_pct:
            return POMatchFlag.qty_mismatch.value
        if quantity_invoiced > 0 and quantity_received > 0:
            inv_diff_pct = abs(quantity_received - quantity_invoiced) / quantity_received * 100
            if inv_diff_pct > tolerance_pct:
                return POMatchFlag.inv_mismatch.value
        return POMatchFlag.ok.value
