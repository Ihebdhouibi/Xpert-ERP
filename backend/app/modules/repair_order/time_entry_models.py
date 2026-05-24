from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class ROTimeEntry(Base):
    __tablename__ = "ro_time_entry"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ro_time_entry_ro_id", "ro_id"),
        Index("ix_ro_time_entry_ro_user", "ro_id", "user_id"),
    )


class ROComment(Base):
    __tablename__ = "ro_comment"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_ro_comment_ro_id", "ro_id"),
        Index("ix_ro_comment_ro_created", "ro_id", "created_at"),
    )
