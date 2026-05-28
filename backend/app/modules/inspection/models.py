from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from typing import Any, Optional

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
from app.core.types import BigIntPK, JsonB


class InspectionItemStatus(str, enum.Enum):
    ok = "ok"
    attention = "attention"
    defective = "defective"
    not_applicable = "not_applicable"


class InspectionStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


INSPECTION_ALLOWED_TRANSITIONS: dict[InspectionStatus, set[InspectionStatus]] = {
    InspectionStatus.draft: {InspectionStatus.in_progress, InspectionStatus.cancelled},
    InspectionStatus.in_progress: {InspectionStatus.completed, InspectionStatus.cancelled},
    InspectionStatus.completed: set(),
    InspectionStatus.cancelled: set(),
}


def can_transition_inspection(from_status: InspectionStatus, to_status: InspectionStatus) -> bool:
    return to_status in INSPECTION_ALLOWED_TRANSITIONS.get(from_status, set())


class InspectionTemplate(Base):
    __tablename__ = "inspection_template"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sections: Mapped[Any] = mapped_column(JsonB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    inspections: Mapped[list[Inspection]] = relationship(
        "Inspection", back_populates="template"
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_inspection_template_public_id"),
        Index("ix_inspection_template_garage", "garage_id"),
    )


class Inspection(Base):
    __tablename__ = "inspection"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    repair_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inspection_template.id", ondelete="RESTRICT"), nullable=False
    )
    mechanic_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("vehicle.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus, name="inspection_status_enum"),
        nullable=False,
        default=InspectionStatus.draft,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    template: Mapped[InspectionTemplate] = relationship(
        "InspectionTemplate", back_populates="inspections"
    )
    results: Mapped[list[InspectionItemResult]] = relationship(
        "InspectionItemResult", back_populates="inspection", cascade="all, delete-orphan"
    )
    conflict_log: Mapped[list[InspectionConflictLog]] = relationship(
        "InspectionConflictLog", back_populates="inspection", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_inspection_public_id"),
        Index("ix_inspection_garage_status", "garage_id", "status"),
        Index("ix_inspection_repair_order", "repair_order_id"),
        Index("ix_inspection_mechanic", "mechanic_id"),
        Index("ix_inspection_vehicle", "vehicle_id"),
    )


class InspectionItemResult(Base):
    __tablename__ = "inspection_item_result"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inspection.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[InspectionItemStatus] = mapped_column(
        Enum(InspectionItemStatus, name="inspection_item_status_enum"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_ids: Mapped[Any] = mapped_column(JsonB, nullable=False, default=list)
    written_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    inspection: Mapped[Inspection] = relationship("Inspection", back_populates="results")

    __table_args__ = (
        UniqueConstraint("inspection_id", "item_id", name="uq_inspection_item_result_item"),
        Index("ix_inspection_item_result_inspection", "inspection_id"),
    )


class InspectionConflictLog(Base):
    __tablename__ = "inspection_conflict_log"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inspection.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_written_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_written_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discarded_status: Mapped[str] = mapped_column(String(50), nullable=False)
    kept_status: Mapped[str] = mapped_column(String(50), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    inspection: Mapped[Inspection] = relationship("Inspection", back_populates="conflict_log")

    __table_args__ = (
        Index("ix_inspection_conflict_log_inspection", "inspection_id"),
    )


class VehicleRecommendation(Base):
    __tablename__ = "vehicle_recommendation"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vehicle_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehicle.id", ondelete="CASCADE"), nullable=False
    )
    source_inspection_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("inspection.id", ondelete="SET NULL"), nullable=True
    )
    item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    item_label: Mapped[str] = mapped_column(String(500), nullable=False)
    item_status: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="archived")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_vehicle_recommendation_public_id"),
        Index("ix_vehicle_recommendation_vehicle", "vehicle_id"),
        Index("ix_vehicle_recommendation_garage_vehicle", "garage_id", "vehicle_id"),
    )


class InspectionApprovalToken(Base):
    __tablename__ = "inspection_approval_token"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    inspection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inspection.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("jti", name="uq_inspection_approval_token_jti"),
        Index("ix_inspection_approval_token_inspection", "inspection_id"),
    )
