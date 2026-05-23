from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.repair_order.models import (
    RepairOrder,
    ROLaborLine,
    ROPartLine,
    ROStatus,
    ROStatusEvent,
)


class RepairOrderRepository:
    """Repository for repair order queries."""

    @staticmethod
    async def get_by_id(
        db: AsyncSession, garage_id: int, ro_id: int, include_deleted: bool = False
    ) -> RepairOrder | None:
        """Get repair order by internal ID."""
        stmt = select(RepairOrder).where(
            RepairOrder.garage_id == garage_id, RepairOrder.id == ro_id
        )
        if not include_deleted:
            stmt = stmt.where(RepairOrder.deleted_at.is_(None))
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_by_public_id(
        db: AsyncSession, garage_id: int, public_id: str, include_deleted: bool = False
    ) -> RepairOrder | None:
        """Get repair order by public UUID."""
        import uuid

        try:
            public_id_uuid = uuid.UUID(public_id)
        except (ValueError, AttributeError):
            return None

        stmt = select(RepairOrder).where(
            RepairOrder.garage_id == garage_id, RepairOrder.public_id == public_id_uuid
        )
        if not include_deleted:
            stmt = stmt.where(RepairOrder.deleted_at.is_(None))
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        status: ROStatus | None = None,
        customer_id: int | None = None,
        vehicle_id: int | None = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RepairOrder], int]:
        """List repair orders with optional filters and pagination."""
        stmt = select(RepairOrder).where(RepairOrder.garage_id == garage_id)

        if not include_deleted:
            stmt = stmt.where(RepairOrder.deleted_at.is_(None))
        if status:
            stmt = stmt.where(RepairOrder.status == status)
        if customer_id:
            stmt = stmt.where(RepairOrder.customer_id == customer_id)
        if vehicle_id:
            stmt = stmt.where(RepairOrder.vehicle_id == vehicle_id)

        # Count total
        count_stmt = select(RepairOrder).where(RepairOrder.garage_id == garage_id)
        if not include_deleted:
            count_stmt = count_stmt.where(RepairOrder.deleted_at.is_(None))
        if status:
            count_stmt = count_stmt.where(RepairOrder.status == status)
        if customer_id:
            count_stmt = count_stmt.where(RepairOrder.customer_id == customer_id)
        if vehicle_id:
            count_stmt = count_stmt.where(RepairOrder.vehicle_id == vehicle_id)

        from sqlalchemy import func

        total = (
            await db.execute(select(func.count()).select_from(count_stmt.subquery()))
        ).scalar()

        # Pagination
        stmt = stmt.order_by(RepairOrder.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)

        rows = (await db.execute(stmt)).scalars().unique().all()
        return rows, total or 0

    @staticmethod
    async def count_by_status(
        db: AsyncSession, garage_id: int, status: ROStatus
    ) -> int:
        """Count active repair orders by status."""
        from sqlalchemy import func

        stmt = (
            select(func.count(RepairOrder.id))
            .where(RepairOrder.garage_id == garage_id)
            .where(RepairOrder.status == status)
            .where(RepairOrder.deleted_at.is_(None))
        )
        return (await db.execute(stmt)).scalar() or 0

    @staticmethod
    async def get_labor_lines(
        db: AsyncSession, ro_id: int
    ) -> list[ROLaborLine]:
        """Get all labor lines for a repair order."""
        stmt = select(ROLaborLine).where(ROLaborLine.ro_id == ro_id)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def get_part_lines(
        db: AsyncSession, ro_id: int
    ) -> list[ROPartLine]:
        """Get all part lines for a repair order."""
        stmt = select(ROPartLine).where(ROPartLine.ro_id == ro_id)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def get_status_history(
        db: AsyncSession, ro_id: int
    ) -> list[ROStatusEvent]:
        """Get status change history for a repair order."""
        stmt = select(ROStatusEvent).where(ROStatusEvent.ro_id == ro_id).order_by(
            ROStatusEvent.occurred_at.asc()
        )
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def add_labor_line(
        db: AsyncSession,
        ro_id: int,
        labor_type: str,
        duration_minutes: int,
        rate_minor: int,
        amount_minor: int,
        created_by_user_id: int | None = None,
    ) -> ROLaborLine:
        """Add a labor line to a repair order."""
        line = ROLaborLine(
            ro_id=ro_id,
            labor_type=labor_type,
            duration_minutes=duration_minutes,
            rate_minor=rate_minor,
            amount_minor=amount_minor,
            created_by_user_id=created_by_user_id,
        )
        db.add(line)
        await db.flush()
        return line

    @staticmethod
    async def add_part_line(
        db: AsyncSession,
        ro_id: int,
        part_name: str,
        quantity: int,
        unit_cost_minor: int,
        amount_minor: int,
        created_by_user_id: int | None = None,
    ) -> ROPartLine:
        """Add a part line to a repair order."""
        line = ROPartLine(
            ro_id=ro_id,
            part_name=part_name,
            quantity=quantity,
            unit_cost_minor=unit_cost_minor,
            amount_minor=amount_minor,
            created_by_user_id=created_by_user_id,
        )
        db.add(line)
        await db.flush()
        return line

    @staticmethod
    async def remove_labor_line(db: AsyncSession, line_id: int) -> bool:
        """Remove a labor line."""
        stmt = select(ROLaborLine).where(ROLaborLine.id == line_id)
        line = (await db.execute(stmt)).scalar_one_or_none()
        if line:
            await db.delete(line)
            await db.flush()
            return True
        return False

    @staticmethod
    async def remove_part_line(db: AsyncSession, line_id: int) -> bool:
        """Remove a part line."""
        stmt = select(ROPartLine).where(ROPartLine.id == line_id)
        line = (await db.execute(stmt)).scalar_one_or_none()
        if line:
            await db.delete(line)
            await db.flush()
            return True
        return False

    @staticmethod
    async def add_status_event(
        db: AsyncSession,
        ro_id: int,
        old_status: ROStatus | None,
        new_status: ROStatus,
        created_by_user_id: int | None = None,
    ) -> ROStatusEvent:
        """Record a status change event."""
        event = ROStatusEvent(
            ro_id=ro_id,
            old_status=old_status.value if old_status else None,
            new_status=new_status.value,
            created_by_user_id=created_by_user_id,
        )
        db.add(event)
        await db.flush()
        return event
