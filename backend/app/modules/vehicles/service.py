"""Vehicle service — business logic, constraints, ownership transfer, re-registration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.vehicles import repository as repo
from app.modules.vehicles.models import (
    Vehicle,
    VehicleOwnershipHistory,
    VehicleRegistrationAlias,
    VehicleStatus,
)
from app.modules.vehicles.schemas import (
    OwnershipTransferRequest,
    ReRegistrationRequest,
    VehicleCreateRequest,
    VehicleHistoryOut,
    VehicleListResponse,
    VehicleOut,
    VehicleROSummary,
    VehicleUpdateRequest,
)

logger = get_logger("vehicles.service")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_vehicle(
    db: AsyncSession,
    *,
    garage_id: int,
    data: VehicleCreateRequest,
    created_by: Optional[int] = None,
) -> VehicleOut:
    logger.info("create_vehicle_start", garage_id=garage_id, make=data.make, model=data.model, registration=data.registration, vin=data.vin)
    try:
        # Uniqueness checks
        if data.registration:
            existing = await repo.get_by_registration(
                db, garage_id=garage_id, registration=data.registration
            )
            if existing:
                raise DuplicateVehicleError(
                    f"A vehicle with registration '{data.registration}' already exists in this garage"
                )

        if data.vin:
            existing = await repo.get_by_vin(db, garage_id=garage_id, vin=data.vin)
            if existing:
                raise DuplicateVehicleError(
                    f"A vehicle with VIN '{data.vin}' already exists in this garage"
                )

        vehicle = Vehicle(
            garage_id=garage_id,
            customer_id=data.customer_id,
            registration=data.registration,
            vin=data.vin,
            make=data.make,
            model=data.model,
            trim=data.trim,
            year=data.year,
            fuel_type=data.fuel_type.value if data.fuel_type else None,
            color=data.color,
            mileage_current=data.mileage_current,
            technical_inspection_due_at=data.technical_inspection_due_at,
            maintenance_due_at=data.maintenance_due_at,
            status=VehicleStatus.active,
            version=0,
        )

        created = await repo.create(db, vehicle)
        await repo.upsert_custom_make(
            db, garage_id=garage_id, name=data.make, created_by=created_by
        )
        await repo.upsert_custom_model(
            db, garage_id=garage_id, make=data.make, name=data.model, created_by=created_by
        )
        logger.info("vehicle_created", vehicle_id=created.id, garage_id=garage_id)
        return VehicleOut.model_validate(created)
    except DuplicateVehicleError:
        raise
    except Exception:
        logger.exception("create_vehicle_error", garage_id=garage_id, registration=data.registration)
        raise


async def get_vehicle(
    db: AsyncSession, *, vehicle_id: int, garage_id: int
) -> VehicleOut:
    logger.info("get_vehicle_start", vehicle_id=vehicle_id, garage_id=garage_id)
    vehicle = await _get_or_404(db, vehicle_id=vehicle_id, garage_id=garage_id)
    return VehicleOut.model_validate(vehicle)


async def list_vehicles(
    db: AsyncSession,
    *,
    garage_id: int,
    search: Optional[str],
    customer_id: Optional[int],
    status: Optional[VehicleStatus],
    page: int,
    page_size: int,
) -> VehicleListResponse:
    logger.info("list_vehicles_start", garage_id=garage_id)
    offset = (page - 1) * page_size
    vehicles, total = await repo.list_vehicles(
        db,
        garage_id=garage_id,
        search=search,
        customer_id=customer_id,
        status=status,
        offset=offset,
        limit=page_size,
    )
    items = []
    for vehicle, customer_name in vehicles:
        out = VehicleOut.model_validate(vehicle)
        out.customer_name = customer_name
        items.append(out)
    return VehicleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_vehicle(
    db: AsyncSession,
    *,
    vehicle_id: int,
    garage_id: int,
    data: VehicleUpdateRequest,
    expected_version: Optional[int],
    updated_by: Optional[int] = None,
) -> VehicleOut:
    logger.info("update_vehicle_start", vehicle_id=vehicle_id, garage_id=garage_id)
    vehicle = await _get_or_404(db, vehicle_id=vehicle_id, garage_id=garage_id)

    if expected_version is not None and vehicle.version != expected_version:
        raise ConflictError(
            f"Version mismatch: expected {expected_version}, current is {vehicle.version}"
        )

    update_fields = data.model_dump(exclude_unset=True)
    if "fuel_type" in update_fields and update_fields["fuel_type"] is not None:
        update_fields["fuel_type"] = update_fields["fuel_type"].value

    for field, value in update_fields.items():
        setattr(vehicle, field, value)

    vehicle.version += 1
    await db.commit()
    await db.refresh(vehicle)

    if "make" in update_fields:
        await repo.upsert_custom_make(
            db, garage_id=garage_id, name=vehicle.make, created_by=updated_by
        )
    if "model" in update_fields:
        await repo.upsert_custom_model(
            db, garage_id=garage_id, make=vehicle.make, name=vehicle.model, created_by=updated_by
        )

    logger.info("vehicle_updated", vehicle_id=vehicle_id, garage_id=garage_id)
    return VehicleOut.model_validate(vehicle)


async def delete_vehicle(
    db: AsyncSession,
    *,
    vehicle_id: int,
    garage_id: int,
    deleted_by: Optional[int],
) -> None:
    logger.info("delete_vehicle_start", vehicle_id=vehicle_id, garage_id=garage_id)
    vehicle = await _get_or_404(db, vehicle_id=vehicle_id, garage_id=garage_id)
    await repo.soft_delete(db, vehicle=vehicle, deleted_by=deleted_by)
    logger.info("vehicle_deleted", vehicle_id=vehicle_id, garage_id=garage_id)


# ---------------------------------------------------------------------------
# Ownership transfer
# ---------------------------------------------------------------------------

async def transfer_ownership(
    db: AsyncSession,
    *,
    vehicle_id: int,
    garage_id: int,
    data: OwnershipTransferRequest,
    transferred_by: Optional[int],
) -> VehicleOut:
    """Transfer vehicle to a new owner.

    Historical repair orders keep their own customer_id reference and are
    unaffected — this only updates vehicle.customer_id.
    """
    logger.info("transfer_ownership_start", vehicle_id=vehicle_id, garage_id=garage_id)
    vehicle = await _get_or_404(db, vehicle_id=vehicle_id, garage_id=garage_id)

    previous_customer_id = vehicle.customer_id

    # Record before making the change
    history_entry = VehicleOwnershipHistory(
        vehicle_id=vehicle.id,
        garage_id=garage_id,
        previous_customer_id=previous_customer_id,
        new_customer_id=data.new_customer_id,
        transferred_by=transferred_by,
        note=data.note,
        transferred_at=datetime.now(tz=timezone.utc),
    )
    await repo.add_ownership_history(db, history_entry)

    vehicle.customer_id = data.new_customer_id
    vehicle.version += 1
    await db.commit()
    await db.refresh(vehicle)

    logger.info(
        "vehicle_ownership_transferred",
        vehicle_id=vehicle_id,
        from_customer=previous_customer_id,
        to_customer=data.new_customer_id,
    )
    return VehicleOut.model_validate(vehicle)


# ---------------------------------------------------------------------------
# Re-registration (alias)
# ---------------------------------------------------------------------------

async def re_register(
    db: AsyncSession,
    *,
    vehicle_id: int,
    garage_id: int,
    data: ReRegistrationRequest,
) -> VehicleOut:
    """Track a plate change: save old plate as alias, update vehicle.registration.

    The vehicle is NOT replaced — it stays the same record with history.
    """
    logger.info("re_register_start", vehicle_id=vehicle_id, garage_id=garage_id)
    vehicle = await _get_or_404(db, vehicle_id=vehicle_id, garage_id=garage_id)

    # Check the new registration is not already taken by another vehicle
    if data.new_registration != vehicle.registration:
        collision = await repo.get_by_registration(
            db, garage_id=garage_id, registration=data.new_registration
        )
        if collision:
            raise DuplicateVehicleError(
                f"Registration '{data.new_registration}' is already assigned to another vehicle"
            )

    # Archive the old plate as an alias
    if vehicle.registration:
        alias = VehicleRegistrationAlias(
            vehicle_id=vehicle.id,
            garage_id=garage_id,
            registration=vehicle.registration,
            valid_until=datetime.now(tz=timezone.utc),
            note=data.note,
        )
        await repo.add_registration_alias(db, alias)

    vehicle.registration = data.new_registration
    vehicle.version += 1
    await db.commit()
    await db.refresh(vehicle)

    logger.info(
        "vehicle_re_registered",
        vehicle_id=vehicle_id,
        new_registration=data.new_registration,
    )
    return VehicleOut.model_validate(vehicle)


# ---------------------------------------------------------------------------
# Custom make / model lookup (user-confirmed dropdown entries)
# ---------------------------------------------------------------------------

async def list_makes(db: AsyncSession, *, garage_id: int) -> list[str]:
    return await repo.list_custom_makes(db, garage_id=garage_id)


async def list_models(db: AsyncSession, *, garage_id: int, make: str) -> list[str]:
    return await repo.list_custom_models(db, garage_id=garage_id, make=make)


async def remove_make(db: AsyncSession, *, garage_id: int, name: str) -> None:
    found = await repo.delete_custom_make(db, garage_id=garage_id, name=name)
    if not found:
        raise MakeModelNotFoundError(name)


async def remove_model(db: AsyncSession, *, garage_id: int, make: str, name: str) -> None:
    found = await repo.delete_custom_model(db, garage_id=garage_id, make=make, name=name)
    if not found:
        raise MakeModelNotFoundError(name)


# ---------------------------------------------------------------------------
# History view
# ---------------------------------------------------------------------------

async def get_vehicle_history(
    db: AsyncSession, *, vehicle_id: int, garage_id: int
) -> VehicleHistoryOut:
    vehicle = await _get_or_404(db, vehicle_id=vehicle_id, garage_id=garage_id)

    ownership_history = await repo.get_ownership_history(
        db, vehicle_id=vehicle_id, garage_id=garage_id
    )
    registration_aliases = await repo.get_registration_aliases(
        db, vehicle_id=vehicle_id, garage_id=garage_id
    )

    # Lazy import to avoid circular dependency with repair_order module
    from sqlalchemy import select
    from app.modules.repair_order.models import RepairOrder

    ro_result = await db.execute(
        select(RepairOrder)
        .where(
            RepairOrder.vehicle_id == vehicle_id,
            RepairOrder.garage_id == garage_id,
            RepairOrder.deleted_at.is_(None),
        )
        .order_by(RepairOrder.created_at.desc())
        .limit(20)
    )
    ros = ro_result.scalars().all()

    return VehicleHistoryOut(
        vehicle=VehicleOut.model_validate(vehicle),
        ownership_history=[
            _ownership_out(h) for h in ownership_history
        ],
        registration_aliases=[
            _alias_out(a) for a in registration_aliases
        ],
        repair_orders=[VehicleROSummary.model_validate(ro) for ro in ros],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_404(
    db: AsyncSession, *, vehicle_id: int, garage_id: int
) -> Vehicle:
    vehicle = await repo.get_by_id(db, vehicle_id=vehicle_id, garage_id=garage_id)
    if vehicle is None:
        raise VehicleNotFoundError(vehicle_id)
    return vehicle


def _ownership_out(h: VehicleOwnershipHistory) -> dict:
    return {
        "id": h.id,
        "vehicle_id": h.vehicle_id,
        "previous_customer_id": h.previous_customer_id,
        "new_customer_id": h.new_customer_id,
        "transferred_by": h.transferred_by,
        "note": h.note,
        "transferred_at": h.transferred_at,
    }


def _alias_out(a: VehicleRegistrationAlias) -> dict:
    return {
        "id": a.id,
        "registration": a.registration,
        "valid_until": a.valid_until,
        "note": a.note,
        "created_at": a.created_at,
    }


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class VehicleNotFoundError(ValueError):
    def __init__(self, vehicle_id: int) -> None:
        super().__init__(f"Vehicle {vehicle_id} not found")
        self.vehicle_id = vehicle_id


class DuplicateVehicleError(ValueError):
    pass


class ConflictError(ValueError):
    pass


class MakeModelNotFoundError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"'{name}' not found in the custom list")
        self.name = name
