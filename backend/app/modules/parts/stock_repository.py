from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.parts.stock_models import (
    LowStockAlert,
    StockLevel,
    StockMovement,
    StockMovementType,
)


class StockRepository:
    @staticmethod
    async def get_or_create_level(
        db: AsyncSession, garage_id: int, part_id: int
    ) -> StockLevel:
        """Get the stock level row, creating it if it does not exist yet.

        Uses SELECT … FOR UPDATE so concurrent writes on PostgreSQL serialise
        through this row-level lock.  SQLite's table-level locking provides the
        same guarantee in tests.
        """
        result = await db.execute(
            select(StockLevel)
            .where(StockLevel.garage_id == garage_id, StockLevel.part_id == part_id)
            .with_for_update()
        )
        level = result.scalar_one_or_none()
        if level is None:
            level = StockLevel(garage_id=garage_id, part_id=part_id)
            db.add(level)
            await db.flush()
            # Re-fetch with lock after insert to ensure we hold it
            result = await db.execute(
                select(StockLevel)
                .where(StockLevel.garage_id == garage_id, StockLevel.part_id == part_id)
                .with_for_update()
            )
            level = result.scalar_one()
        return level

    @staticmethod
    async def get_level(
        db: AsyncSession, garage_id: int, part_id: int
    ) -> Optional[StockLevel]:
        result = await db.execute(
            select(StockLevel).where(
                StockLevel.garage_id == garage_id,
                StockLevel.part_id == part_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_levels(
        db: AsyncSession, garage_id: int, low_stock_only: bool = False
    ) -> list[StockLevel]:
        stmt = select(StockLevel).where(StockLevel.garage_id == garage_id)
        result = await db.execute(stmt)
        levels = list(result.scalars().all())
        return levels

    @staticmethod
    async def create_movement(
        db: AsyncSession,
        garage_id: int,
        part_id: int,
        movement_type: StockMovementType,
        quantity: int,
        unit_cost_minor: Optional[int],
        ref_type: Optional[str],
        ref_id: Optional[str],
        reason: Optional[str],
        created_by_user_id: Optional[int],
    ) -> StockMovement:
        mv = StockMovement(
            garage_id=garage_id,
            part_id=part_id,
            type=movement_type,
            quantity=quantity,
            unit_cost_minor=unit_cost_minor,
            ref_type=ref_type,
            ref_id=ref_id,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        db.add(mv)
        await db.flush()
        return mv

    @staticmethod
    async def list_movements(
        db: AsyncSession,
        garage_id: int,
        part_id: Optional[int] = None,
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StockMovement]:
        stmt = (
            select(StockMovement)
            .where(StockMovement.garage_id == garage_id)
            .order_by(StockMovement.created_at.desc())
        )
        if part_id is not None:
            stmt = stmt.where(StockMovement.part_id == part_id)
        if ref_type is not None:
            stmt = stmt.where(StockMovement.ref_type == ref_type)
        if ref_id is not None:
            stmt = stmt.where(StockMovement.ref_id == ref_id)
        stmt = stmt.offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_net_reserved_for_ref(
        db: AsyncSession,
        garage_id: int,
        ref_type: str,
        ref_id: str,
    ) -> dict[int, int]:
        """Return {part_id: net_reserved} for all reservation/release movements
        with the given ref, so we know how much to release on cancellation."""
        res_stmt = (
            select(
                StockMovement.part_id,
                func.sum(StockMovement.quantity).label("qty"),
            )
            .where(
                StockMovement.garage_id == garage_id,
                StockMovement.ref_type == ref_type,
                StockMovement.ref_id == ref_id,
                StockMovement.type == StockMovementType.reservation,
            )
            .group_by(StockMovement.part_id)
        )
        rel_stmt = (
            select(
                StockMovement.part_id,
                func.sum(StockMovement.quantity).label("qty"),
            )
            .where(
                StockMovement.garage_id == garage_id,
                StockMovement.ref_type == ref_type,
                StockMovement.ref_id == ref_id,
                StockMovement.type == StockMovementType.release,
            )
            .group_by(StockMovement.part_id)
        )
        res_result = await db.execute(res_stmt)
        rel_result = await db.execute(rel_stmt)
        reserved = {row.part_id: row.qty for row in res_result}
        released = {row.part_id: row.qty for row in rel_result}
        net: dict[int, int] = {}
        for part_id, qty in reserved.items():
            net_qty = qty - released.get(part_id, 0)
            if net_qty > 0:
                net[part_id] = net_qty
        return net

    # ------------------------------------------------------------------
    # Low-stock alerts
    # ------------------------------------------------------------------

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        garage_id: int,
        part_id: int,
        on_hand: int,
        threshold: int,
        suggested_supplier_id: Optional[int] = None,
        suggested_reorder_quantity: Optional[int] = None,
    ) -> LowStockAlert:
        alert = LowStockAlert(
            garage_id=garage_id,
            part_id=part_id,
            on_hand=on_hand,
            threshold=threshold,
            suggested_supplier_id=suggested_supplier_id,
            suggested_reorder_quantity=suggested_reorder_quantity,
        )
        db.add(alert)
        await db.flush()
        return alert

    @staticmethod
    async def list_alerts(
        db: AsyncSession,
        garage_id: int,
        status: Optional[str] = None,
        include_resolved: bool = False,
    ) -> list[LowStockAlert]:
        from app.modules.parts.stock_models import LowStockAlertStatus
        stmt = select(LowStockAlert).where(LowStockAlert.garage_id == garage_id)
        if status is not None:
            stmt = stmt.where(LowStockAlert.status == status)
        elif not include_resolved:
            stmt = stmt.where(LowStockAlert.status != LowStockAlertStatus.resolved)
        stmt = stmt.order_by(LowStockAlert.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_alert(
        db: AsyncSession, garage_id: int, alert_id: int
    ) -> Optional[LowStockAlert]:
        result = await db.execute(
            select(LowStockAlert).where(
                LowStockAlert.id == alert_id,
                LowStockAlert.garage_id == garage_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def acknowledge_alert(db: AsyncSession, alert: LowStockAlert) -> LowStockAlert:
        from app.modules.parts.stock_models import LowStockAlertStatus
        alert.status = LowStockAlertStatus.acknowledged
        await db.flush()
        return alert

    @staticmethod
    async def resolve_alert(db: AsyncSession, alert: LowStockAlert) -> LowStockAlert:
        from app.modules.parts.stock_models import LowStockAlertStatus
        alert.status = LowStockAlertStatus.resolved
        await db.flush()
        return alert
