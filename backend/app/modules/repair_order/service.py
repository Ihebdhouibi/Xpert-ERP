from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.audit.service import audit
from app.modules.repair_order.models import (
    RepairOrder,
    ROStatus,
    can_transition,
    is_backward_transition,
)
from app.modules.repair_order.repository import RepairOrderRepository

logger = get_logger("repair_order.service")


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


class StepIncompleteError(Exception):
    """Raised when a status transition is blocked by unmet step preconditions."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class RepairOrderNotFoundError(Exception):
    """Raised when repair order is not found."""

    pass


class RepairOrderLineStateError(Exception):
    """Raised when a line cannot be modified in the repair order's current status."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class PartLineNotFoundError(Exception):
    """Raised when a part line is not found on the repair order."""

    pass


class LaborLineNotFoundError(Exception):
    """Raised when a labor line is not found on the repair order."""

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
        description: Optional[str],
        priority: Optional[str] = None,
        estimated_cost_minor: Optional[int] = None,
        estimated_cost_currency: Optional[str] = None,
    ) -> RepairOrder:
        """Create a new repair order in 'created' status."""
        logger.info("create_repair_order_start", garage_id=garage_id, customer_id=customer_id, user_id=user_id)
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

        logger.info(
            "repair_order_created",
            ro_public_id=str(ro.public_id),
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            garage_id=garage_id,
            user_id=user_id,
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
        logger.info("update_repair_order_start", public_id=public_id, garage_id=garage_id, user_id=user_id)
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

        logger.info("update_repair_order_success", ro_public_id=public_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def transition_status(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        new_status: ROStatus,
        reason: Optional[str] = None,
        allow_negative_stock: bool = False,
    ) -> RepairOrder:
        """Transition repair order to a new status.

        When transitioning to in_repair, all pending stock reservations are
        atomically converted to committed out movements.  If any part has
        insufficient stock (and allow_negative_stock=False), NegativeStockError
        is raised and the whole transition is rolled back.
        """
        logger.info("transition_status_start", public_id=public_id, new_status=new_status.value, garage_id=garage_id, user_id=user_id)
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        # Validate transition
        if not can_transition(ro.status, new_status):
            raise InvalidStatusTransitionError(ro.status, new_status)

        backward = is_backward_transition(ro.status, new_status)
        if backward and not (reason and reason.strip()):
            raise StepIncompleteError(
                "Un motif est requis pour revenir au statut précédent."
            )

        # Step preconditions: diagnosis can only move to repair once a mechanic
        # has accepted the job and the diagnosis form is completed.
        if ro.status == ROStatus.diagnosis and new_status == ROStatus.in_repair:
            missing: list[str] = []
            if ro.assigned_user_id is None:
                missing.append("affecter un mécanicien")
            elif ro.assignment_accepted_at is None:
                missing.append("faire accepter l'affectation")
            if ro.diagnosis_completed_at is None:
                missing.append("terminer le diagnostic")
            if missing:
                raise StepIncompleteError(
                    "Étape diagnostic incomplète : " + ", ".join(missing) + "."
                )

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

        # Commit stock reservations when work begins
        if new_status == ROStatus.in_repair:
            from app.modules.parts.stock_service import commit_reservations_for_ref
            await commit_reservations_for_ref(
                db,
                garage_id=garage_id,
                ref_type="repair_order",
                ref_id=str(ro.public_id),
                created_by_user_id=user_id,
                allow_negative=allow_negative_stock,
            )

        # Reverse the stock committed on in_repair entry when moving back to diagnosis
        if old_status == ROStatus.in_repair and new_status == ROStatus.diagnosis:
            from app.modules.parts.stock_service import reverse_commit_for_ref
            await reverse_commit_for_ref(
                db,
                garage_id=garage_id,
                ref_type="repair_order",
                ref_id=str(ro.public_id),
                created_by_user_id=user_id,
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

        logger.info(
            "repair_order_status_transition",
            ro_public_id=str(ro.public_id),
            old_status=old_status.value,
            new_status=new_status.value,
            garage_id=garage_id,
            user_id=user_id,
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
        from decimal import Decimal, ROUND_HALF_UP
        from app.core.constants import TVA_PCT
        logger.info("add_labor_line_start", public_id=public_id, garage_id=garage_id, user_id=user_id)
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        amount_minor = int(
            (Decimal(rate_minor) * (Decimal("1") + TVA_PCT / Decimal("100")))
            .to_integral_value(rounding=ROUND_HALF_UP)
        )
        await RepairOrderRepository.add_labor_line(
            db, ro.id, labor_type, duration_minutes, rate_minor, amount_minor, user_id,
            tva_pct=float(TVA_PCT),
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

        logger.info("add_labor_line_success", ro_public_id=public_id, garage_id=garage_id)
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
        remise_pct: float = 0,
        tva_pct: float = 0,  # ignored — backend always uses TVA_PCT
        part_public_id: Optional[str] = None,
    ) -> RepairOrder:
        """Add a part line and recalculate total cost.

        If part_public_id is provided (catalog-linked line), the UUID is
        resolved to an internal part_id and a stock reservation is created
        atomically in the same transaction.
        """
        from decimal import Decimal, ROUND_HALF_UP
        from app.core.constants import TVA_PCT
        logger.info("add_part_line_start", public_id=public_id, garage_id=garage_id, user_id=user_id)
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")

        # Resolve catalog part if given
        resolved_part_id: Optional[int] = None
        if part_public_id is not None:
            from app.modules.parts.repository import PartRepository
            part = await PartRepository.get_by_public_id(db, garage_id, part_public_id)
            if part is None:
                raise RepairOrderNotFoundError(f"Part {part_public_id} not found")
            resolved_part_id = part.id

        effective_tva = float(TVA_PCT)
        amount_minor = int(
            (Decimal(quantity) * Decimal(unit_cost_minor)
             * (Decimal("1") - Decimal(str(remise_pct)) / Decimal("100"))
             * (Decimal("1") + TVA_PCT / Decimal("100")))
            .to_integral_value(rounding=ROUND_HALF_UP)
        )
        await RepairOrderRepository.add_part_line(
            db, ro.id, part_name, quantity, unit_cost_minor, amount_minor, user_id,
            part_id=resolved_part_id,
            remise_pct=remise_pct,
            tva_pct=effective_tva,
        )

        # Reserve stock for catalog-linked parts
        if resolved_part_id is not None:
            from app.modules.parts.stock_service import reserve_for_ref
            await reserve_for_ref(
                db,
                garage_id=garage_id,
                part_id=resolved_part_id,
                quantity=quantity,
                ref_type="repair_order",
                ref_id=str(ro.public_id),
                reason=f"Reserved for RO part line: {part_name}",
                created_by_user_id=user_id,
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
                "part_id": resolved_part_id,
                "part_name": part_name,
                "quantity": quantity,
                "amount_minor": amount_minor,
                "actual_cost_minor": ro.actual_cost_minor,
            },
        )

        logger.info("add_part_line_success", ro_public_id=public_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def update_labor_line(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        line_id: int,
        labor_type: str,
        duration_minutes: int,
        rate_minor: int,
    ) -> RepairOrder:
        """Update a labor line. Only allowed while the RO is in diagnosis or in_repair."""
        from decimal import Decimal, ROUND_HALF_UP
        from app.core.constants import TVA_PCT
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")
        if ro.status not in (ROStatus.diagnosis, ROStatus.in_repair):
            raise RepairOrderLineStateError(
                "La main d'œuvre ne peut être modifiée qu'en statut Diagnostic ou En réparation."
            )
        line = await RepairOrderRepository.get_labor_line(db, line_id)
        if not line or line.ro_id != ro.id:
            raise LaborLineNotFoundError(f"Labor line {line_id} not found")

        old_value = {
            "labor_type": line.labor_type,
            "duration_minutes": line.duration_minutes,
            "rate_minor": line.rate_minor,
        }
        amount_minor = int(
            (Decimal(rate_minor) * (Decimal("1") + TVA_PCT / Decimal("100")))
            .to_integral_value(rounding=ROUND_HALF_UP)
        )
        line.labor_type = labor_type
        line.duration_minutes = duration_minutes
        line.rate_minor = rate_minor
        line.amount_minor = amount_minor
        await db.flush()

        await _recalculate_cost(db, ro)

        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="update_labor_line",
            entity_type="repair_order",
            entity_id=ro.id,
            old_value=old_value,
            new_value={
                "labor_type": labor_type,
                "duration_minutes": duration_minutes,
                "rate_minor": rate_minor,
                "amount_minor": amount_minor,
            },
        )
        logger.info("update_labor_line_success", ro_public_id=public_id, line_id=line_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def remove_labor_line(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        line_id: int,
    ) -> RepairOrder:
        """Remove a labor line. Only allowed while the RO is in diagnosis or in_repair."""
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")
        if ro.status not in (ROStatus.diagnosis, ROStatus.in_repair):
            raise RepairOrderLineStateError(
                "La main d'œuvre ne peut être supprimée qu'en statut Diagnostic ou En réparation."
            )
        line = await RepairOrderRepository.get_labor_line(db, line_id)
        if not line or line.ro_id != ro.id:
            raise LaborLineNotFoundError(f"Labor line {line_id} not found")

        old_value = {
            "labor_type": line.labor_type,
            "duration_minutes": line.duration_minutes,
            "rate_minor": line.rate_minor,
        }
        await RepairOrderRepository.remove_labor_line(db, line_id)
        await _recalculate_cost(db, ro)

        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="remove_labor_line",
            entity_type="repair_order",
            entity_id=ro.id,
            old_value=old_value,
        )
        logger.info("remove_labor_line_success", ro_public_id=public_id, line_id=line_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def update_part_line(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        line_id: int,
        quantity: int,
        unit_cost_minor: int,
        remise_pct: float = 0,
    ) -> RepairOrder:
        """Update a part line's quantity/price/discount, adjusting stock reservation
        to match. Only allowed while the RO is en attente de pièces (paused_parts).
        """
        from decimal import Decimal, ROUND_HALF_UP
        from app.core.constants import TVA_PCT
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")
        if ro.status != ROStatus.paused_parts:
            raise RepairOrderLineStateError(
                "Les pièces ne peuvent être modifiées qu'en statut En attente de pièces."
            )
        line = await RepairOrderRepository.get_part_line(db, line_id)
        if not line or line.ro_id != ro.id:
            raise PartLineNotFoundError(f"Part line {line_id} not found")

        old_value = {
            "quantity": line.quantity,
            "unit_cost_minor": line.unit_cost_minor,
            "remise_pct": float(line.remise_pct),
        }
        old_quantity = line.quantity

        amount_minor = int(
            (Decimal(quantity) * Decimal(unit_cost_minor)
             * (Decimal("1") - Decimal(str(remise_pct)) / Decimal("100"))
             * (Decimal("1") + TVA_PCT / Decimal("100")))
            .to_integral_value(rounding=ROUND_HALF_UP)
        )
        line.quantity = quantity
        line.unit_cost_minor = unit_cost_minor
        line.remise_pct = remise_pct
        line.amount_minor = amount_minor
        await db.flush()

        if line.part_id is not None and quantity != old_quantity:
            await _adjust_stock_for_line_quantity_change(
                db,
                garage_id=garage_id,
                ro=ro,
                part_id=line.part_id,
                delta=quantity - old_quantity,
                user_id=user_id,
                reason=f"Adjusted RO part line: {line.part_name}",
            )

        await _recalculate_cost(db, ro)

        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="update_part_line",
            entity_type="repair_order",
            entity_id=ro.id,
            old_value=old_value,
            new_value={
                "quantity": quantity,
                "unit_cost_minor": unit_cost_minor,
                "remise_pct": remise_pct,
                "amount_minor": amount_minor,
            },
        )
        logger.info("update_part_line_success", ro_public_id=public_id, line_id=line_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def remove_part_line(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
        line_id: int,
    ) -> RepairOrder:
        """Remove a part line, releasing/restocking its stock reservation.
        Only allowed while the RO is en attente de pièces (paused_parts).
        """
        ro = await RepairOrderRepository.get_by_public_id(db, garage_id, public_id)
        if not ro:
            raise RepairOrderNotFoundError(f"Repair order {public_id} not found")
        if ro.status != ROStatus.paused_parts:
            raise RepairOrderLineStateError(
                "Les pièces ne peuvent être supprimées qu'en statut En attente de pièces."
            )
        line = await RepairOrderRepository.get_part_line(db, line_id)
        if not line or line.ro_id != ro.id:
            raise PartLineNotFoundError(f"Part line {line_id} not found")

        old_value = {
            "part_id": line.part_id,
            "part_name": line.part_name,
            "quantity": line.quantity,
        }
        part_id = line.part_id
        quantity = line.quantity
        part_name = line.part_name

        await RepairOrderRepository.remove_part_line(db, line_id)

        if part_id is not None:
            await _adjust_stock_for_line_quantity_change(
                db,
                garage_id=garage_id,
                ro=ro,
                part_id=part_id,
                delta=-quantity,
                user_id=user_id,
                reason=f"Removed RO part line: {part_name}",
            )

        await _recalculate_cost(db, ro)

        await audit(
            db,
            garage_id=garage_id,
            user_id=user_id,
            component="repair_order",
            action="remove_part_line",
            entity_type="repair_order",
            entity_id=ro.id,
            old_value=old_value,
        )
        logger.info("remove_part_line_success", ro_public_id=public_id, line_id=line_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def soft_delete_repair_order(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
    ) -> RepairOrder:
        """Soft delete repair order (idempotent)."""
        logger.info("soft_delete_repair_order_start", public_id=public_id, garage_id=garage_id, user_id=user_id)
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

        logger.info("soft_delete_repair_order_success", ro_public_id=public_id, garage_id=garage_id)
        return ro

    @staticmethod
    async def restore_repair_order(
        db: AsyncSession,
        garage_id: int,
        user_id: int,
        public_id: str,
    ) -> RepairOrder:
        """Restore a soft-deleted repair order."""
        logger.info("restore_repair_order_start", public_id=public_id, garage_id=garage_id, user_id=user_id)
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

        logger.info("restore_repair_order_success", ro_public_id=public_id, garage_id=garage_id)
        return ro


async def _adjust_stock_for_line_quantity_change(
    db: AsyncSession,
    garage_id: int,
    ro: RepairOrder,
    part_id: int,
    delta: int,
    user_id: int,
    reason: str,
) -> None:
    """Adjust the stock footprint of a catalog-linked RO part line by `delta`
    units (positive = need more stock reserved, negative = give stock back).

    Reservations for an RO are tracked in aggregate per (RO, part) in the
    stock movement ledger, not per line. When giving stock back we must first
    cancel whatever is still just "reserved" (added since the last in_repair
    commit) and only fall back to restocking the remainder as an "in"
    movement for the portion that was already committed to an actual
    stock-out in an earlier in_repair cycle (the RO can cycle through
    in_repair <-> paused_parts multiple times).
    """
    from app.modules.parts.stock_service import reserve_for_ref, release_for_ref, record_movement
    from app.modules.parts.stock_models import StockMovementType
    from app.modules.parts.stock_repository import StockRepository

    ref_type = "repair_order"
    ref_id = str(ro.public_id)

    if delta > 0:
        await reserve_for_ref(
            db, garage_id=garage_id, part_id=part_id, quantity=delta,
            ref_type=ref_type, ref_id=ref_id, reason=reason, created_by_user_id=user_id,
        )
        return
    if delta == 0:
        return

    to_release = -delta
    net_reserved = await StockRepository.get_net_reserved_for_ref(db, garage_id, ref_type, ref_id)
    still_reserved = net_reserved.get(part_id, 0)

    from_reservation = min(to_release, still_reserved)
    if from_reservation > 0:
        await release_for_ref(
            db, garage_id=garage_id, part_id=part_id, quantity=from_reservation,
            ref_type=ref_type, ref_id=ref_id, reason=reason, created_by_user_id=user_id,
        )

    remainder = to_release - from_reservation
    if remainder > 0:
        # Already committed to an actual stock-out in an earlier in_repair
        # cycle. Use the same reason literal that get_net_committed_for_ref
        # matches on, so a later backward transition out of in_repair
        # computes the correct remaining committed quantity for this part.
        await record_movement(
            db, garage_id=garage_id, part_id=part_id, movement_type=StockMovementType.in_,
            quantity=remainder, ref_type=ref_type, ref_id=ref_id,
            reason="Reversed on in_repair backward transition",
            created_by_user_id=user_id,
        )


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
