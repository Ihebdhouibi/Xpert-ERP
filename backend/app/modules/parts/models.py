from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class PartStatus(str, enum.Enum):
    active = "active"
    discontinued = "discontinued"
    out_of_stock = "out_of_stock"


class PartCategory(Base):
    __tablename__ = "part_category"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("part_category.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    parent: Mapped[Optional[PartCategory]] = relationship(
        "PartCategory", back_populates="children", remote_side="PartCategory.id"
    )
    children: Mapped[list[PartCategory]] = relationship(
        "PartCategory", back_populates="parent"
    )
    parts: Mapped[list[Part]] = relationship("Part", back_populates="category")

    __table_args__ = (
        Index("ix_part_category_garage_id", "garage_id"),
        Index("ix_part_category_parent_id", "parent_id"),
        UniqueConstraint("garage_id", "name", "parent_id", name="uq_part_category_garage_name_parent"),
    )


class Part(Base):
    __tablename__ = "part"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sku_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("part_category.id", ondelete="SET NULL"), nullable=True
    )
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")
    purchase_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    selling_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_hint_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    reorder_threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reorder_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[PartStatus] = mapped_column(
        Enum(PartStatus, name="part_status_enum"),
        nullable=False,
        default=PartStatus.active,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped[Optional[PartCategory]] = relationship(
        "PartCategory", back_populates="parts"
    )
    equivalents_as_a: Mapped[list[PartEquivalent]] = relationship(
        "PartEquivalent",
        foreign_keys="PartEquivalent.part_a_id",
        cascade="all, delete-orphan",
    )
    equivalents_as_b: Mapped[list[PartEquivalent]] = relationship(
        "PartEquivalent",
        foreign_keys="PartEquivalent.part_b_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_part_public_id"),
        Index(
            "uq_part_garage_sku",
            "garage_id",
            "sku_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_part_garage_id", "garage_id"),
        Index("ix_part_garage_sku", "garage_id", "sku_code"),
        Index("ix_part_garage_category", "garage_id", "category_id"),
        Index("ix_part_garage_status", "garage_id", "status"),
    )


class PartEquivalent(Base):
    __tablename__ = "part_equivalent"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    part_a_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="CASCADE"), nullable=False
    )
    part_b_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("part.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    part_a: Mapped[Part] = relationship(
        "Part", foreign_keys=[part_a_id], overlaps="equivalents_as_a"
    )
    part_b: Mapped[Part] = relationship(
        "Part", foreign_keys=[part_b_id], overlaps="equivalents_as_b"
    )

    __table_args__ = (
        UniqueConstraint("part_a_id", "part_b_id", name="uq_part_equivalent_pair"),
        CheckConstraint("part_a_id < part_b_id", name="ck_part_equivalent_ordered"),
        Index("ix_part_equivalent_a", "part_a_id"),
        Index("ix_part_equivalent_b", "part_b_id"),
    )
