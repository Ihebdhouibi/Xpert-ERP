"""Vehicle repository — all DB queries for the vehicle module."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vehicles.models import (
    Vehicle,
    VehicleOwnershipHistory,
    VehicleRegistrationAlias,
    VehicleStatus,
)


# ---------------------------------------------------------------------------
# Vehicle CRUD
# ---------------------------------------------------------------------------

async def create(db: AsyncSession, vehicle: Vehicle) -> Vehicle:
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


async def get_by_id(
    db: AsyncSession, *, vehicle_id: int, garage_id: int
) -> Optional[Vehicle]:
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.garage_id == garage_id,
            Vehicle.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_by_registration(
    db: AsyncSession, *, garage_id: int, registration: str
) -> Optional[Vehicle]:
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.garage_id == garage_id,
            Vehicle.registration == registration,
            Vehicle.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_by_vin(
    db: AsyncSession, *, garage_id: int, vin: str
) -> Optional[Vehicle]:
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.garage_id == garage_id,
            Vehicle.vin == vin,
            Vehicle.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_vehicles(
    db: AsyncSession,
    *,
    garage_id: int,
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
    status: Optional[VehicleStatus] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Vehicle], int]:
    base_filter = [
        Vehicle.garage_id == garage_id,
        Vehicle.deleted_at.is_(None),
    ]

    if search:
        q = f"%{search}%"
        base_filter.append(
            or_(Vehicle.registration.ilike(q), Vehicle.vin.ilike(q))
        )

    if customer_id is not None:
        base_filter.append(Vehicle.customer_id == customer_id)

    if status is not None:
        base_filter.append(Vehicle.status == status)

    count_result = await db.execute(
        select(func.count(Vehicle.id)).where(*base_filter)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Vehicle)
        .where(*base_filter)
        .order_by(Vehicle.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def soft_delete(
    db: AsyncSession, *, vehicle: Vehicle, deleted_by: Optional[int]
) -> None:
    vehicle.deleted_at = datetime.now(tz=timezone.utc)
    vehicle.deleted_by = deleted_by
    await db.commit()


# ---------------------------------------------------------------------------
# Ownership history
# ---------------------------------------------------------------------------

async def add_ownership_history(
    db: AsyncSession, entry: VehicleOwnershipHistory
) -> VehicleOwnershipHistory:
    db.add(entry)
    await db.flush()
    return entry


async def get_ownership_history(
    db: AsyncSession, *, vehicle_id: int, garage_id: int
) -> list[VehicleOwnershipHistory]:
    result = await db.execute(
        select(VehicleOwnershipHistory)
        .where(
            VehicleOwnershipHistory.vehicle_id == vehicle_id,
            VehicleOwnershipHistory.garage_id == garage_id,
        )
        .order_by(VehicleOwnershipHistory.transferred_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Registration aliases
# ---------------------------------------------------------------------------

async def add_registration_alias(
    db: AsyncSession, alias: VehicleRegistrationAlias
) -> VehicleRegistrationAlias:
    db.add(alias)
    await db.flush()
    return alias


async def get_registration_aliases(
    db: AsyncSession, *, vehicle_id: int, garage_id: int
) -> list[VehicleRegistrationAlias]:
    result = await db.execute(
        select(VehicleRegistrationAlias)
        .where(
            VehicleRegistrationAlias.vehicle_id == vehicle_id,
            VehicleRegistrationAlias.garage_id == garage_id,
        )
        .order_by(VehicleRegistrationAlias.created_at.desc())
    )
    return list(result.scalars().all())


async def patch_from_ocr(
    db: AsyncSession,
    *,
    vehicle_id: int,
    garage_id: int,
    fields: dict[str, str],
) -> bool:
    """Apply confirmed OCR fields to a vehicle row.

    Returns True if the vehicle was found and updated, False otherwise.
    Only updates fields that are present and non-empty in *fields*.
    """
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.garage_id == garage_id,
            Vehicle.deleted_at.is_(None),
        )
    )
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        return False

    # OCR field → vehicle column mapping
    str_mapping = {
        "immatriculation": "registration",
        "vin": "vin",
        "marque": "make",
        "modele": "model",
    }
    for ocr_field, col in str_mapping.items():
        value = fields.get(ocr_field, "").strip()
        if value:
            setattr(vehicle, col, value)

    # Extract 4-digit year from date_mise_en_circulation (e.g. "01/01/2019")
    date_str = fields.get("date_mise_en_circulation", "")
    if date_str:
        match = re.search(r"\b(19|20)\d{2}\b", date_str)
        if match:
            vehicle.year = int(match.group())

    await db.commit()
    return True
