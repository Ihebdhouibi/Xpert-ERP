"""Document sequence ORM model.

One row per (garage_id, doc_type, year).  The row is locked with SELECT FOR
UPDATE inside a transaction so that concurrent callers always get a unique,
gap-free number.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK


class DocumentSequence(Base):
    __tablename__ = "document_sequence"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # QUOT, INV, CRNOTE, DO  (max 10 chars)
    doc_type: Mapped[str] = mapped_column(String(10), nullable=False)

    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Monotonically increasing counter; starts at 0, incremented before use
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("garage_id", "doc_type", "year", name="uq_sequence_garage_type_year"),
    )
