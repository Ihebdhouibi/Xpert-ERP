"""
GarageSetting — runtime-tunable CFG_* values stored in the database.

garage_id = 0 means the value is a global default (no specific garage).
Per-garage overrides use the actual garage_id.  The service reads
the per-garage row first, falls back to garage_id=0, then to the
pydantic-settings env value.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK


class GarageSetting(Base):
    __tablename__ = "garage_setting"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("garage_id", "key", name="uq_garage_setting_garage_key"),
        Index("ix_garage_setting_garage_id", "garage_id"),
        Index("ix_garage_setting_key", "key"),
    )
