from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import audit
from app.modules.repair_order.models import (
    RepairOrder,
    ROStatus,
    can_transition,
)
from app.modules.repair_order.repository import RepairOrderRepository


class OptimisticLockError(Exception):
    """Raised when optimistic lock version mismatch is detected."""

    def __init__(self, current_version: int, submitted_version: int):
        self.current_version = current_version
        self.submitted_version = submitted_version
        super().__init__(
            f"Version mismatch: current={current_version}, submitted={submitted_version}"
        )


class InvalidStatusTransitionError(Exception):
    """Raised when attempting an invalid status transition."""

    def __init__(self, from_status: ROStatus, to_status: ROStatus):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Cannot transition from {from_status.value} to {to_status.value}"
        )


class RepairOrderNotFoundError(Exception):
    """Raised when repair order is not found."""

    pass


class RepairOrderService:
    """Service layer for repair order business logic."""

    @staticmethod
    async def create_repair_order(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        customer_id: int,
        vehicle_id: Optional[int],
        description: str,
        priority: Optional[str] = None,
        estimated_cost_minor: Optional[int] = None,
        estimated_cost_currency: Optional[str] = None,
    ) -> RepairOrder:
        """Create a new repair order in 'created' status."""
        ro = RepairOrder(
            garage_id=garage_id,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            description=description,
            priority=priority,
            estimated_cost_minor=estimated_cost_minor,
            estimated_cost_currency=estimated_cost_currency,
            status=ROStatus.created,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
        )
        db.add(ro)
        await db.flush()

        # Record status event (no old_status for creation)
        await RepairOrderRepository.add_status_event(
            db, ro.id, None, ROStatus.created, user_id
        )

        # Audit
        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="create",
            entity_type="repair_order",
            entity_id=ro.id,
            new_value=_to_audit_dict(ro),
        )

        return ro

    @staticmethod
    async def update_repair_order(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        submitted_version: int,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        estimated_cost_minor: Optional[int] = None,
        estimated_cost_currency: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> RepairOrder:
        """Update repair order with optimistic locking."""
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        # Optimistic locking
        if ro.version != submitted_version:
            raise OptimisticLockError(ro.version, submitted_version)

        # Store old value for audit
        old_value = _to_audit_dict(ro)

        # Update fields
        if description is not None:
            ro.description = description
        if priority is not None:
            ro.priority = priority
        if estimated_cost_minor is not None:
            ro.estimated_cost_minor = estimated_cost_minor
        if estimated_cost_currency is not None:
            ro.estimated_cost_currency = estimated_cost_currency
        if notes is not None:
            ro.notes = notes

        ro.version += 1
        ro.updated_at = datetime.now()
        ro.updated_by_user_id = user_id
        await db.flush()

        # Audit
        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="update",
            entity_type="repair_order",
            entity_id=ro.id,
            old_value=old_value,
            new_value=_to_audit_dict(ro),
        )

        return ro

    @staticmethod
    async def transition_status(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        new_status: ROStatus,
        reason: Optional[str] = None,
    ) -> RepairOrder:
        """Transition repair order to a new status."""
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        # Validate transition
        if not can_transition(ro.status, new_status):
            raise InvalidStatusTransitionError(ro.status, new_status)

        old_status = ro.status
        ro.status = new_status
        ro.version += 1
        ro.updated_at = datetime.now()
        ro.updated_by_user_id = user_id
        await db.flush()

        # Record status event
        await RepairOrderRepository.add_status_event(
            db, ro.id, old_status, new_status, user_id
        )

        # Audit
        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="status_transition",
            entity_type="repair_order",
            entity_id=ro.id,
            reason=reason or f"Transitioned from {old_status.value} to {new_status.value}",
            new_value={"status": new_status.value},
        )

        return ro

    @staticmethod
    async def add_labor_line(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        labor_type: str,
        duration_minutes: int,
        rate_minor: int,
    ) -> RepairOrder:
        """Add a labor line and recalculate total cost."""
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        amount_minor = duration_minutes * rate_minor
        await RepairOrderRepository.add_labor_line(
            db, ro.id, labor_type, duration_minutes, rate_minor, amount_minor, user_id
        )

        # Recalculate actual cost
        await _recalculate_cost(db, ro)

        # Audit
        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="add_labor_line",
            entity_type="repair_order",
            entity_id=ro.id,
            new_value={
                "labor_type": labor_type,
                "duration_minutes": duration_minutes,
                "amount_minor": amount_minor,
                "actual_cost_minor": ro.actual_cost_minor,
            },
        )

        return ro

    @staticmethod
    async def add_part_line(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        part_name: str,
        quantity: int,
        unit_cost_minor: int,
    ) -> RepairOrder:
        """Add a part line and recalculate total cost."""
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        amount_minor = quantity * unit_cost_minor
        await RepairOrderRepository.add_part_line(
            db, ro.id, part_name, quantity, unit_cost_minor, amount_minor, user_id
        )

        # Recalculate actual cost
        await _recalculate_cost(db, ro)

        # Audit
        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="add_part_line",
            entity_type="repair_order",
            entity_id=ro.id,
            new_value={
                "part_name": part_name,
                "quantity": quantity,
                "amount_minor": amount_minor,
                "actual_cost_minor": ro.actual_cost_minor,
            },
        )

        return ro

    @staticmethod
    async def soft_delete_repair_order(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
    ) -> RepairOrder:
        """Soft delete repair order (idempotent)."""
        ro = await RepairOrderRepository.get_by_public_id(
            db, garage_id, public_id, include_deleted=True
        )
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        if not ro.deleted_at:
            ro.deleted_at = datetime.now()
            ro.updated_by_user_id = user_id
            await db.flush()

            await audit(
                db,
                garage_id=garage_id,
                user_id=user_id,
                component="repair_order",
                action="soft_delete",
                entity_type="repair_order",
                entity_id=ro.id,
            )

        return ro

    @staticmethod
    async def restore_repair_order(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
    ) -> RepairOrder:
        """Restore a soft-deleted repair order."""
        ro = await RepairOrderRepository.get_by_public_id(
            db, garage_id, public_id, include_deleted=True
        )
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        if ro.deleted_at:
            ro.deleted_at = None
            ro.updated_by_user_id = user_id
            await db.flush()

            await audit(
                db,
                garage_id=garage_id,
                user_id=user_id,
                component="repair_order",
                action="restore",
                entity_type="repair_order",
                entity_id=ro.id,
            )

        return ro


async def _recalculate_cost(db: AsyncSession, ro: RepairOrder) -> None:
    """Recalculate and update actual_cost_minor from line items."""
    labor_lines = await RepairOrderRepository.get_labor_lines(db, ro.id)
    part_lines = await RepairOrderRepository.get_part_lines(db, ro.id)

    labor_total = sum(line.amount_minor for line in labor_lines)
    part_total = sum(line.amount_minor for line in part_lines)

    ro.actual_cost_minor = labor_total + part_total
    ro.version += 1
    ro.updated_at = datetime.now()
    await db.flush()


def _to_audit_dict(ro: RepairOrder) -> dict:
    """Convert repair order to audit-safe dict."""
    return {
        "id": ro.id,
        "public_id": str(ro.public_id),
        "customer_id": ro.customer_id,
        "vehicle_id": ro.vehicle_id,
        "description": ro.description,
        "status": ro.status.value,
        "priority": ro.priority,
        "estimated_cost_minor": ro.estimated_cost_minor,
        "estimated_cost_currency": ro.estimated_cost_currency,
        "actual_cost_minor": ro.actual_cost_minor,
        "notes": ro.notes,
        "version": ro.version,
    }
