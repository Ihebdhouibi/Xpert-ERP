from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.parts.models import Part
from app.modules.parts.repository import PartRepository
from app.modules.parts.stock_models import LowStockAlert, StockLevel, StockMovement, StockMovementType
from app.modules.parts.stock_repository import StockRepository


class NegativeStockError(Exception):
    """Raised when an out movement would make available stock go negative."""

    def __init__(self, available: int, requested: int) -> None:
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock: available={available}, requested={requested}"
        )


class InvalidMovementError(Exception):
    pass


async def record_movement(
    db: AsyncSession,
    garage_id: int,
    part_id: int,
    movement_type: StockMovementType,
    quantity: int,
    unit_cost_minor: Optional[int] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    reason: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    allow_negative: bool = False,
) -> StockMovement:
    """Record a stock movement and update the aggregation table atomically."""
    # Validate quantity sign constraints
    if movement_type in (
        StockMovementType.in_,
        StockMovementType.out,
        StockMovementType.reservation,
        StockMovementType.release,
    ):
        if quantity <= 0:
            raise InvalidMovementError(
                f"Quantity must be positive for movement type '{movement_type.value}'"
            )
    elif movement_type == StockMovementType.adjustment:
        if quantity == 0:
            raise InvalidMovementError("Adjustment quantity cannot be zero")

    # Lock and fetch the stock level row
    level = await StockRepository.get_or_create_level(db, garage_id, part_id)

    # Negative stock guard for 'out' movements
    if movement_type == StockMovementType.out:
        available = level.on_hand - level.reserved
        if available < quantity and not allow_negative:
            raise NegativeStockError(available, quantity)

    # Apply the movement to the aggregation row
    _apply_movement(level, movement_type, quantity, unit_cost_minor)
    level.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Persist the ledger entry
    movement = await StockRepository.create_movement(
        db,
        garage_id=garage_id,
        part_id=part_id,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost_minor=unit_cost_minor,
        ref_type=ref_type,
        ref_id=ref_id,
        reason=reason,
        created_by_user_id=created_by_user_id,
    )

    # Low-stock alert — check after any movement that can reduce on_hand
    if movement_type in (
        StockMovementType.out,
        StockMovementType.adjustment,
    ):
        await _maybe_create_alert(db, garage_id, part_id, level.on_hand)

    return movement


def _apply_movement(
    level: StockLevel,
    movement_type: StockMovementType,
    quantity: int,
    unit_cost_minor: Optional[int],
) -> None:
    """Mutate level in-place. Does NOT flush — caller is responsible."""
    if movement_type == StockMovementType.in_:
        if unit_cost_minor is not None and unit_cost_minor >= 0:
            if level.on_hand > 0:
                # Weighted average cost update
                level.avg_cost_minor = (
                    level.on_hand * level.avg_cost_minor + quantity * unit_cost_minor
                ) // (level.on_hand + quantity)
            else:
                level.avg_cost_minor = unit_cost_minor
        level.on_hand += quantity

    elif movement_type == StockMovementType.out:
        level.on_hand -= quantity

    elif movement_type == StockMovementType.adjustment:
        # Signed delta; can be positive or negative
        level.on_hand += quantity

    elif movement_type == StockMovementType.reservation:
        level.reserved += quantity

    elif movement_type == StockMovementType.release:
        level.reserved = max(0, level.reserved - quantity)


async def _maybe_create_alert(
    db: AsyncSession,
    garage_id: int,
    part_id: int,
    on_hand: int,
) -> None:
    from sqlalchemy import select
    from app.modules.parts.models import Part

    result = await db.execute(
        select(Part.reorder_threshold).where(Part.id == part_id)
    )
    row = result.first()
    if row and row[0] is not None and on_hand <= row[0]:
        await StockRepository.create_alert(
            db, garage_id=garage_id, part_id=part_id,
            on_hand=on_hand, threshold=row[0],
        )


# ---------------------------------------------------------------------------
# Reservation helpers
# ---------------------------------------------------------------------------

async def reserve_for_ref(
    db: AsyncSession,
    garage_id: int,
    part_id: int,
    quantity: int,
    ref_type: str,
    ref_id: str,
    reason: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
) -> StockMovement:
    return await record_movement(
        db,
        garage_id=garage_id,
        part_id=part_id,
        movement_type=StockMovementType.reservation,
        quantity=quantity,
        ref_type=ref_type,
        ref_id=ref_id,
        reason=reason,
        created_by_user_id=created_by_user_id,
    )


async def release_for_ref(
    db: AsyncSession,
    garage_id: int,
    part_id: int,
    quantity: int,
    ref_type: str,
    ref_id: str,
    reason: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
) -> StockMovement:
    return await record_movement(
        db,
        garage_id=garage_id,
        part_id=part_id,
        movement_type=StockMovementType.release,
        quantity=quantity,
        ref_type=ref_type,
        ref_id=ref_id,
        reason=reason,
        created_by_user_id=created_by_user_id,
    )


async def release_all_for_ref(
    db: AsyncSession,
    garage_id: int,
    ref_type: str,
    ref_id: str,
    created_by_user_id: Optional[int] = None,
) -> list[StockMovement]:
    """Release all net-reserved stock for a given reference (e.g. an RO).

    Called inside the RO cancellation transaction so that both the soft-delete
    and the reservation release are committed atomically.
    """
    net = await StockRepository.get_net_reserved_for_ref(
        db, garage_id, ref_type, ref_id
    )
    released: list[StockMovement] = []
    for part_id, qty in net.items():
        mv = await release_for_ref(
            db,
            garage_id=garage_id,
            part_id=part_id,
            quantity=qty,
            ref_type=ref_type,
            ref_id=ref_id,
            reason=f"Auto-released on {ref_type} cancellation",
            created_by_user_id=created_by_user_id,
        )
        released.append(mv)
    return released
