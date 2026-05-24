"""Cash session repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash_session.models import CashSession, CashSessionStatus


async def create(db: AsyncSession, session: CashSession) -> None:
    db.add(session)
    await db.flush()


async def get_by_id(
    db: AsyncSession, session_id: int, garage_id: int
) -> Optional[CashSession]:
    result = await db.execute(
        select(CashSession).where(
            CashSession.id == session_id,
            CashSession.garage_id == garage_id,
        )
    )
    return result.scalar_one_or_none()


async def get_open_session(
    db: AsyncSession, garage_id: int
) -> Optional[CashSession]:
    """Return the current open session for a garage, or None."""
    result = await db.execute(
        select(CashSession).where(
            CashSession.garage_id == garage_id,
            CashSession.status == CashSessionStatus.open,
        )
    )
    return result.scalar_one_or_none()


async def list_by_garage(
    db: AsyncSession, garage_id: int, *, page: int = 1, page_size: int = 25
) -> tuple[list[CashSession], int]:
    from sqlalchemy import func as sqlfunc

    count_result = await db.execute(
        select(sqlfunc.count()).select_from(CashSession).where(
            CashSession.garage_id == garage_id
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(CashSession)
        .where(CashSession.garage_id == garage_id)
        .order_by(CashSession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def save(db: AsyncSession, session: CashSession) -> None:
    db.add(session)
    await db.flush()
