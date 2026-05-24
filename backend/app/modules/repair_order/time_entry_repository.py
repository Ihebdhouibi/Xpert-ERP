from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .time_entry_models import ROComment, ROTimeEntry


# ---------------------------------------------------------------------------
# Time Entry
# ---------------------------------------------------------------------------

async def get_open_entry(
    db: AsyncSession, ro_id: int, user_id: int
) -> Optional[ROTimeEntry]:
    result = await db.execute(
        select(ROTimeEntry).where(
            ROTimeEntry.ro_id == ro_id,
            ROTimeEntry.user_id == user_id,
            ROTimeEntry.ended_at.is_(None),
        )
    )
    return result.scalars().first()


async def start_entry(
    db: AsyncSession, ro_id: int, user_id: int, notes: Optional[str] = None
) -> ROTimeEntry:
    entry = ROTimeEntry(ro_id=ro_id, user_id=user_id, notes=notes)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def stop_entry(
    db: AsyncSession,
    entry: ROTimeEntry,
    ended_at: datetime,
    duration_minutes: int,
    notes: Optional[str] = None,
) -> ROTimeEntry:
    entry.ended_at = ended_at
    entry.duration_minutes = duration_minutes
    if notes is not None:
        entry.notes = notes
    await db.flush()
    await db.refresh(entry)
    return entry


async def list_entries(db: AsyncSession, ro_id: int) -> list[ROTimeEntry]:
    result = await db.execute(
        select(ROTimeEntry)
        .where(ROTimeEntry.ro_id == ro_id)
        .order_by(ROTimeEntry.started_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

async def create_comment(
    db: AsyncSession, ro_id: int, user_id: int, body: str
) -> ROComment:
    comment = ROComment(ro_id=ro_id, user_id=user_id, body=body)
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return comment


async def list_comments(
    db: AsyncSession, ro_id: int, include_deleted: bool = False
) -> list[ROComment]:
    q = select(ROComment).where(ROComment.ro_id == ro_id)
    if not include_deleted:
        q = q.where(ROComment.deleted_at.is_(None))
    q = q.order_by(ROComment.created_at.asc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_comment_by_id(
    db: AsyncSession, comment_id: int
) -> Optional[ROComment]:
    result = await db.execute(
        select(ROComment).where(ROComment.id == comment_id)
    )
    return result.scalars().first()


async def update_comment(
    db: AsyncSession, comment: ROComment, body: str
) -> ROComment:
    comment.body = body
    comment.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(comment)
    return comment


async def soft_delete_comment(
    db: AsyncSession, comment: ROComment
) -> ROComment:
    comment.deleted_at = datetime.utcnow()
    await db.flush()
    await db.refresh(comment)
    return comment
