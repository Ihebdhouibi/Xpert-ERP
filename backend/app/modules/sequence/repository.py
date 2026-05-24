"""Document sequence repository.

The core operation (next()) MUST be called inside an open transaction and uses
SELECT FOR UPDATE to prevent concurrent callers from receiving the same number.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sequence.models import DocumentSequence


async def get_sequence(
    db: AsyncSession,
    *,
    garage_id: int,
    doc_type: str,
    year: int,
    with_lock: bool = False,
) -> Optional[DocumentSequence]:
    stmt = select(DocumentSequence).where(
        DocumentSequence.garage_id == garage_id,
        DocumentSequence.doc_type == doc_type,
        DocumentSequence.year == year,
    )
    if with_lock:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_sequences(
    db: AsyncSession, *, garage_id: int
) -> list[DocumentSequence]:
    result = await db.execute(
        select(DocumentSequence)
        .where(DocumentSequence.garage_id == garage_id)
        .order_by(DocumentSequence.doc_type, DocumentSequence.year.desc())
    )
    return list(result.scalars().all())


async def create_sequence(
    db: AsyncSession,
    *,
    garage_id: int,
    doc_type: str,
    year: int,
) -> DocumentSequence:
    seq = DocumentSequence(garage_id=garage_id, doc_type=doc_type, year=year, last_number=0)
    db.add(seq)
    await db.flush()
    return seq
