"""Document sequence service.

next() is the only public entry point that mutates state.  It MUST be called
inside a transaction that is committed by the caller so that the lock is
released atomically with the surrounding business operation.

Usage inside another service:

    async with db.begin():           # or join an existing transaction
        ref = await sequence_service.next(db, garage_id=gid, doc_type="INV")
    # ref.formatted → "INV-2026-00001"
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.sequence import repository as repo
from app.modules.sequence.schemas import NextNumberOut

logger = get_logger("sequence.service")

# Number format: {TYPE}-{YEAR}-{SEQ:05d}
# Configurable via CFG_DOC_NUMBER_FORMAT in a future settings-table lookup.
_DEFAULT_FORMAT = "{doc_type}-{year}-{seq:05d}"


async def next(
    db: AsyncSession,
    *,
    garage_id: int,
    doc_type: str,
) -> NextNumberOut:
    """Atomically increment and return the next document number.

    Caller is responsible for the surrounding transaction.  The SELECT FOR
    UPDATE row lock prevents concurrent callers from receiving the same number.
    On SQLite (tests) FOR UPDATE is a no-op; tests run single-threaded so this
    is safe.
    """
    doc_type = doc_type.upper()
    year = datetime.now(tz=timezone.utc).year

    seq = await repo.get_sequence(db, garage_id=garage_id, doc_type=doc_type, year=year, with_lock=True)

    if seq is None:
        seq = await repo.create_sequence(db, garage_id=garage_id, doc_type=doc_type, year=year)

    seq.last_number += 1
    await db.flush()

    formatted = _DEFAULT_FORMAT.format(doc_type=doc_type, year=year, seq=seq.last_number)

    logger.info(
        "sequence_issued",
        garage_id=garage_id,
        doc_type=doc_type,
        year=year,
        number=seq.last_number,
        formatted=formatted,
    )

    return NextNumberOut(
        doc_type=doc_type,
        year=year,
        number=seq.last_number,
        formatted=formatted,
    )


async def peek(
    db: AsyncSession,
    *,
    garage_id: int,
) -> list:
    """Read-only: list current counters for all doc types for this garage."""
    from app.modules.sequence.schemas import SequenceStateOut
    rows = await repo.list_sequences(db, garage_id=garage_id)
    return [SequenceStateOut.model_validate(r) for r in rows]
