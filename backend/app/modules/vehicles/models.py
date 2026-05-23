"""Vehicle ORM models — Vehicle, ownership history, registration aliases."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK


class FuelType(str, enum.Enum):
    gasoline = "gasoline"
    diesel = "diesel"
    hybrid = "hybrid"
    ev = "ev"
    lpg = "lpg"
    cng = "cng"


class VehicleStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    scrapped = "scrapped"


class Vehicle(Base):
    __tablename__ = "vehicle"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Current owner — nullable to support unowned/fleet vehicles
    customer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # At least one of registration / vin must be set (enforced in service layer)
    registration: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)

    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    fuel_type: Mapped[Optional[str]] = mapped_column(
        Enum(FuelType, name="fuel_type_enum"), nullable=True
    )
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    mileage_current: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_service_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    technical_inspection_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    maintenance_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus, name="vehicle_status_enum"),
        nullable=False,
        default=VehicleStatus.active,
        server_default="active",
    )

    # Optimistic concurrency lock
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        # NULL values are treated as distinct — allows multiple VIN-only vehicles
        UniqueConstraint("garage_id", "registration", name="uq_vehicle_garage_registration"),
        UniqueConstraint("garage_id", "vin", name="uq_vehicle_garage_vin"),
        Index("ix_vehicle_garage_id", "garage_id"),
        Index("ix_vehicle_customer_id", "customer_id"),
    )


class VehicleOwnershipHistory(Base):
    """Immutable record of every ownership transfer for a vehicle."""

    __tablename__ = "vehicle_ownership_history"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    previous_customer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    new_customer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    transferred_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_ownership_history_vehicle_id", "vehicle_id"),
        Index("ix_ownership_history_garage_id", "garage_id"),
    )


class VehicleRegistrationAlias(Base):
    """Previous registration plates — re-registration tracked as alias, not new record."""

    __tablename__ = "vehicle_registration_alias"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # The old plate that was replaced
    registration: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_reg_alias_vehicle_id", "vehicle_id"),
        Index("ix_reg_alias_garage_registration", "garage_id", "registration"),
    )
