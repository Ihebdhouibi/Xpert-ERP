"""Unit tests for repair order service — state machine, cost calculations,
optimistic locking, soft delete / restore, audit hooks."""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.parts.models import Part, PartStatus
from app.modules.parts.stock_repository import StockRepository
from app.modules.parts.stock_service import reserve_for_ref
from app.modules.repair_order.models import (
    RepairOrder,
    ROStatus,
    can_transition,
)
from app.modules.repair_order.service import (
    InvalidStatusTransitionError,
    OptimisticLockError,
    RepairOrderNotFoundError,
    RepairOrderService,
    StepIncompleteError,
)

GARAGE = 1
ACTOR = 1


async def _create_ro(db: AsyncSession, **kwargs) -> RepairOrder:
    """Helper to create a repair order with sane defaults."""
    return await RepairOrderService.create_repair_order(
        db,
        garage_id=kwargs.get("garage_id", GARAGE),
        user_id=kwargs.get("user_id", ACTOR),
        customer_id=kwargs.get("customer_id", 99),
        vehicle_id=kwargs.get("vehicle_id", None),
        description=kwargs.get("description", "Diagnose engine knock"),
        priority=kwargs.get("priority", None),
        estimated_cost_minor=kwargs.get("estimated_cost_minor", None),
        estimated_cost_currency=kwargs.get("estimated_cost_currency", None),
    )


# ---------------------------------------------------------------------------
# State machine unit tests (pure logic, no DB needed)
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_created_can_go_to_diagnosis(self):
        assert can_transition(ROStatus.created, ROStatus.diagnosis)

    def test_created_cannot_go_to_delivered(self):
        assert not can_transition(ROStatus.created, ROStatus.delivered)

    def test_created_cannot_go_to_itself(self):
        assert not can_transition(ROStatus.created, ROStatus.created)

    def test_diagnosis_can_go_to_in_repair(self):
        assert can_transition(ROStatus.diagnosis, ROStatus.in_repair)

    def test_diagnosis_can_go_to_paused_parts(self):
        assert can_transition(ROStatus.diagnosis, ROStatus.paused_parts)

    def test_in_repair_can_go_to_finished(self):
        assert can_transition(ROStatus.in_repair, ROStatus.finished)

    def test_finished_can_go_to_delivered(self):
        assert can_transition(ROStatus.finished, ROStatus.delivered)

    def test_delivered_has_no_transitions(self):
        for status in ROStatus:
            assert not can_transition(ROStatus.delivered, status)

    def test_paused_parts_can_go_back_to_in_repair(self):
        assert can_transition(ROStatus.paused_parts, ROStatus.in_repair)

    def test_paused_approval_can_go_back_to_diagnosis(self):
        assert can_transition(ROStatus.paused_approval, ROStatus.diagnosis)

    def test_all_active_states_can_reach_paused_approval(self):
        pausable = {ROStatus.created, ROStatus.diagnosis, ROStatus.in_repair, ROStatus.finished}
        for status in pausable:
            assert can_transition(status, ROStatus.paused_approval), (
                f"Expected {status} → paused_approval to be allowed"
            )


# ---------------------------------------------------------------------------
# Create repair order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateRepairOrder:
    async def test_creates_with_status_created(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        assert ro.status == ROStatus.created
        assert ro.actual_cost_minor == 0
        assert ro.version == 1
        assert ro.deleted_at is None

    async def test_creates_status_event(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        stmt = select(RepairOrder).where(RepairOrder.id == ro.id)
        fresh = (await db_session.execute(stmt)).scalar_one()
        assert fresh.status == ROStatus.created

    async def test_sets_garage_and_customer_id(self, db_session: AsyncSession):
        ro = await _create_ro(db_session, garage_id=7, customer_id=42)
        assert ro.garage_id == 7
        assert ro.customer_id == 42

    async def test_creates_audit_log(self, db_session: AsyncSession):
        await _create_ro(db_session)
        await db_session.flush()
        count = (await db_session.execute(
            select(AuditLog).where(AuditLog.action == "create")
        )).scalars().all()
        assert len(count) >= 1


# ---------------------------------------------------------------------------
# Update repair order (optimistic locking)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUpdateRepairOrder:
    async def test_update_description_bumps_version(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        updated = await RepairOrderService.update_repair_order(
            db_session, GARAGE, ACTOR, str(ro.public_id), 1,
            description="Updated description",
        )
        assert updated.description == "Updated description"
        assert updated.version == 2

    async def test_stale_version_raises_optimistic_lock_error(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        with pytest.raises(OptimisticLockError) as exc_info:
            await RepairOrderService.update_repair_order(
                db_session, GARAGE, ACTOR, str(ro.public_id), 99,
                description="This should fail",
            )
        assert exc_info.value.current_version == 1
        assert exc_info.value.submitted_version == 99

    async def test_update_nonexistent_raises_not_found(self, db_session: AsyncSession):
        with pytest.raises(RepairOrderNotFoundError):
            await RepairOrderService.update_repair_order(
                db_session, GARAGE, ACTOR, "00000000-0000-0000-0000-000000000000", 1,
            )


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStatusTransition:
    async def test_valid_transition_updates_status(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        updated = await RepairOrderService.transition_status(
            db_session, GARAGE, ACTOR, str(ro.public_id), ROStatus.diagnosis
        )
        assert updated.status == ROStatus.diagnosis
        assert updated.version == 2

    async def test_invalid_transition_raises_error(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            await RepairOrderService.transition_status(
                db_session, GARAGE, ACTOR, str(ro.public_id), ROStatus.delivered
            )
        assert exc_info.value.from_status == ROStatus.created
        assert exc_info.value.to_status == ROStatus.delivered

    async def test_full_lifecycle_transitions(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = str(ro.public_id)

        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.diagnosis)
        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.in_repair)
        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.finished)
        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.delivered)
        assert ro.status == ROStatus.delivered

    async def test_pause_and_resume(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = str(ro.public_id)

        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.diagnosis)
        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.in_repair)
        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.paused_parts)
        ro = await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.in_repair)
        assert ro.status == ROStatus.in_repair

    async def test_transition_not_found_raises_error(self, db_session: AsyncSession):
        with pytest.raises(RepairOrderNotFoundError):
            await RepairOrderService.transition_status(
                db_session, GARAGE, ACTOR,
                "00000000-0000-0000-0000-000000000000", ROStatus.diagnosis
            )


# ---------------------------------------------------------------------------
# Backward transitions — going back to an earlier step
# ---------------------------------------------------------------------------

async def _advance_to_in_repair(db_session: AsyncSession, ro: RepairOrder) -> str:
    """Move a fresh RO to in_repair, satisfying the diagnosis step preconditions."""
    pid = str(ro.public_id)
    await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.diagnosis)
    ro.assigned_user_id = ACTOR
    ro.assignment_accepted_at = datetime.now()
    ro.diagnosis_completed_at = datetime.now()
    await db_session.flush()
    await RepairOrderService.transition_status(db_session, GARAGE, ACTOR, pid, ROStatus.in_repair)
    return pid


@pytest.mark.asyncio
class TestBackwardTransition:
    async def test_backward_transition_requires_reason(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = await _advance_to_in_repair(db_session, ro)

        with pytest.raises(StepIncompleteError):
            await RepairOrderService.transition_status(
                db_session, GARAGE, ACTOR, pid, ROStatus.diagnosis
            )

    async def test_backward_transition_with_reason_succeeds(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = await _advance_to_in_repair(db_session, ro)

        updated = await RepairOrderService.transition_status(
            db_session, GARAGE, ACTOR, pid, ROStatus.diagnosis, reason="Erreur de saisie"
        )
        assert updated.status == ROStatus.diagnosis

    async def test_in_repair_to_diagnosis_reverses_committed_stock(self, db_session: AsyncSession):
        part = Part(
            garage_id=GARAGE,
            sku_code="BACKWARD-TEST-001",
            name="Test Part",
            unit_of_measure="pcs",
            purchase_price_minor=500,
            selling_price_minor=1000,
            status=PartStatus.active,
        )
        db_session.add(part)
        await db_session.flush()

        # Stock: 20 on hand
        level = await StockRepository.get_or_create_level(db_session, GARAGE, part.id)
        level.on_hand = 20
        await db_session.flush()

        ro = await _create_ro(db_session)
        await db_session.flush()

        await reserve_for_ref(
            db_session, garage_id=GARAGE, part_id=part.id, quantity=5,
            ref_type="repair_order", ref_id=str(ro.public_id),
        )
        pid = await _advance_to_in_repair(db_session, ro)

        # Entering in_repair committed the reservation into a stock-out
        level = await StockRepository.get_level(db_session, GARAGE, part.id)
        assert level.on_hand == 15
        assert level.reserved == 0

        # Go back to diagnosis — the committed stock should be reversed
        await RepairOrderService.transition_status(
            db_session, GARAGE, ACTOR, pid, ROStatus.diagnosis, reason="Retour diagnostic"
        )

        level = await StockRepository.get_level(db_session, GARAGE, part.id)
        assert level.on_hand == 20
        assert level.reserved == 5


# ---------------------------------------------------------------------------
# Labor lines + cost calculation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLaborLines:
    async def test_add_labor_line_calculates_amount(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        updated = await RepairOrderService.add_labor_line(
            db_session, GARAGE, ACTOR, str(ro.public_id),
            labor_type="Oil change",
            duration_minutes=0,
            rate_minor=5000,  # 50.00
        )
        # Labor is a flat price: amount = rate (duration is no longer a factor)
        assert updated.actual_cost_minor == 5000

    async def test_multiple_labor_lines_sum_correctly(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = str(ro.public_id)

        await RepairOrderService.add_labor_line(
            db_session, GARAGE, ACTOR, pid, "Labor A", 0, 4000
        )
        updated = await RepairOrderService.add_labor_line(
            db_session, GARAGE, ACTOR, pid, "Labor B", 0, 5000
        )
        # Flat price per line: 4000 + 5000 = 9,000
        assert updated.actual_cost_minor == 9000


# ---------------------------------------------------------------------------
# Part lines + cost calculation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPartLines:
    async def test_add_part_line_calculates_amount(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        updated = await RepairOrderService.add_part_line(
            db_session, GARAGE, ACTOR, str(ro.public_id),
            part_name="Oil Filter",
            quantity=2,
            unit_cost_minor=1500,  # 15.00
        )
        # amount = 2 * 1500 = 3,000
        assert updated.actual_cost_minor == 3000

    async def test_labor_and_part_combined_cost(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = str(ro.public_id)

        await RepairOrderService.add_labor_line(
            db_session, GARAGE, ACTOR, pid, "Labor", 0, 5000
        )  # flat 5,000
        updated = await RepairOrderService.add_part_line(
            db_session, GARAGE, ACTOR, pid, "Filter", 1, 2000
        )  # 2,000
        assert updated.actual_cost_minor == 7000


# ---------------------------------------------------------------------------
# Soft delete / restore
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSoftDelete:
    async def test_soft_delete_sets_deleted_at(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()

        deleted = await RepairOrderService.soft_delete_repair_order(
            db_session, GARAGE, ACTOR, str(ro.public_id)
        )
        assert deleted.deleted_at is not None

    async def test_soft_delete_is_idempotent(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = str(ro.public_id)

        ro1 = await RepairOrderService.soft_delete_repair_order(db_session, GARAGE, ACTOR, pid)
        ro2 = await RepairOrderService.soft_delete_repair_order(db_session, GARAGE, ACTOR, pid)
        assert ro1.deleted_at == ro2.deleted_at

    async def test_restore_clears_deleted_at(self, db_session: AsyncSession):
        ro = await _create_ro(db_session)
        await db_session.flush()
        pid = str(ro.public_id)

        await RepairOrderService.soft_delete_repair_order(db_session, GARAGE, ACTOR, pid)
        restored = await RepairOrderService.restore_repair_order(db_session, GARAGE, ACTOR, pid)
        assert restored.deleted_at is None

    async def test_delete_nonexistent_raises_not_found(self, db_session: AsyncSession):
        with pytest.raises(RepairOrderNotFoundError):
            await RepairOrderService.soft_delete_repair_order(
                db_session, GARAGE, ACTOR, "00000000-0000-0000-0000-000000000000"
            )
