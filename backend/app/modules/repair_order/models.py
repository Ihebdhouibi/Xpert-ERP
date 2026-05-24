from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class ROStatus(str, enum.Enum):
    """Repair order status enum — defines state machine transitions."""
    created = "created"
    diagnosis = "diagnosis"
    in_repair = "in_repair"
    finished = "finished"
    delivered = "delivered"
    paused_parts = "paused_parts"
    paused_approval = "paused_approval"


# State machine: allowed transitions from each status
ALLOWED_TRANSITIONS: dict[ROStatus, set[ROStatus]] = {
    ROStatus.created: {ROStatus.diagnosis, ROStatus.paused_approval},
    ROStatus.diagnosis: {ROStatus.in_repair, ROStatus.paused_parts, ROStatus.paused_approval},
    ROStatus.in_repair: {ROStatus.finished, ROStatus.paused_parts, ROStatus.paused_approval},
    ROStatus.finished: {ROStatus.delivered, ROStatus.paused_approval},
    ROStatus.delivered: set(),
    ROStatus.paused_parts: {ROStatus.in_repair, ROStatus.diagnosis},
    ROStatus.paused_approval: {ROStatus.in_repair, ROStatus.diagnosis, ROStatus.created},
}


def can_transition(from_status: ROStatus, to_status: ROStatus) -> bool:
    """Check if a status transition is allowed."""
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


class RepairOrder(Base):
    __tablename__ = "repair_order"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customer.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("vehicle.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ROStatus] = mapped_column(
        Enum(ROStatus, name="ro_status_enum"),
        nullable=False,
        default=ROStatus.created,
    )
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_cost_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    estimated_cost_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    actual_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    assigned_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    labor_lines: Mapped[list[ROLaborLine]] = relationship(
        "ROLaborLine", back_populates="repair_order", cascade="all, delete-orphan"
    )
    part_lines: Mapped[list[ROPartLine]] = relationship(
        "ROPartLine", back_populates="repair_order", cascade="all, delete-orphan"
    )
    status_events: Mapped[list[ROStatusEvent]] = relationship(
        "ROStatusEvent", back_populates="repair_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_repair_order_public_id"),
        Index("ix_repair_order_garage_status", "garage_id", "status"),
        Index("ix_repair_order_garage_customer", "garage_id", "customer_id"),
        Index("ix_repair_order_garage_vehicle", "garage_id", "vehicle_id"),
        Index("ix_repair_order_garage_created", "garage_id", "created_at"),
    )


class ROLaborLine(Base):
    __tablename__ = "ro_labor_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="CASCADE"), nullable=False
    )

    labor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Relationship
    repair_order: Mapped[RepairOrder] = relationship(
        "RepairOrder", back_populates="labor_lines"
    )

    __table_args__ = (
        Index("ix_ro_labor_line_ro_id", "ro_id"),
    )


class ROPartLine(Base):
    __tablename__ = "ro_part_line"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="CASCADE"), nullable=False
    )

    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Relationship
    repair_order: Mapped[RepairOrder] = relationship(
        "RepairOrder", back_populates="part_lines"
    )

    __table_args__ = (
        Index("ix_ro_part_line_ro_id", "ro_id"),
    )


class ROStatusEvent(Base):
    __tablename__ = "ro_status_event"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="CASCADE"), nullable=False
    )

    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Relationship
    repair_order: Mapped[RepairOrder] = relationship(
        "RepairOrder", back_populates="status_events"
    )

    __table_args__ = (
        Index("ix_ro_status_event_ro_id", "ro_id"),
        Index("ix_ro_status_event_ro_occurred", "ro_id", "occurred_at"),
    )


class ROPhoto(Base):
    __tablename__ = "ro_photo"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="CASCADE"), nullable=False
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_ro_photo_ro_id", "ro_id"),
        Index("ix_ro_photo_garage_ro", "garage_id", "ro_id"),
    )
