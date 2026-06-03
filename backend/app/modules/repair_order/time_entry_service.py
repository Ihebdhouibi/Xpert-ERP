from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from . import time_entry_repository as repo
from .time_entry_models import ROComment, ROTimeEntry

logger = get_logger("repair_order.time_entry")


class TimeEntryAlreadyOpenError(Exception):
    pass


class TimeEntryNotFoundError(Exception):
    pass


class CommentNotFoundError(Exception):
    pass


class CommentForbiddenError(Exception):
    pass


class CommentAlreadyDeletedError(Exception):
    pass


# ---------------------------------------------------------------------------
# Time Entry
# ---------------------------------------------------------------------------

async def start_time_entry(
    db: AsyncSession,
    ro_id: int,
    user_id: int,
    notes: Optional[str] = None,
) -> ROTimeEntry:
    existing = await repo.get_open_entry(db, ro_id, user_id)
    if existing is not None:
        raise TimeEntryAlreadyOpenError(existing.id)
    entry = await repo.start_entry(db, ro_id, user_id, notes)
    await db.commit()
    await db.refresh(entry)
    logger.info("time_entry_started", entry_id=entry.id, ro_id=ro_id, user_id=user_id)
    return entry


async def stop_time_entry(
    db: AsyncSession,
    ro_id: int,
    user_id: int,
    notes: Optional[str] = None,
) -> ROTimeEntry:
    entry = await repo.get_open_entry(db, ro_id, user_id)
    if entry is None:
        raise TimeEntryNotFoundError()

    ended_at = datetime.now(timezone.utc)
    delta = ended_at - entry.started_at.replace(tzinfo=timezone.utc)
    duration_minutes = max(1, int(delta.total_seconds() / 60))

    entry = await repo.stop_entry(db, entry, ended_at, duration_minutes, notes)
    await db.commit()
    await db.refresh(entry)
    logger.info("time_entry_stopped", entry_id=entry.id, ro_id=ro_id, user_id=user_id, duration_minutes=duration_minutes)
    return entry


async def list_time_entries(
    db: AsyncSession, ro_id: int
) -> list[ROTimeEntry]:
    return await repo.list_entries(db, ro_id)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

async def create_comment(
    db: AsyncSession,
    ro_id: int,
    user_id: int,
    body: str,
) -> ROComment:
    comment = await repo.create_comment(db, ro_id, user_id, body)
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_comments(
    db: AsyncSession, ro_id: int
) -> list[ROComment]:
    return await repo.list_comments(db, ro_id, include_deleted=False)


async def update_comment(
    db: AsyncSession,
    comment_id: int,
    requesting_user_id: int,
    body: str,
) -> ROComment:
    comment = await repo.get_comment_by_id(db, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise CommentNotFoundError()
    if comment.user_id != requesting_user_id:
        raise CommentForbiddenError()
    comment = await repo.update_comment(db, comment, body)
    await db.commit()
    await db.refresh(comment)
    return comment


async def delete_comment(
    db: AsyncSession,
    comment_id: int,
    requesting_user_id: int,
    is_admin: bool = False,
) -> None:
    comment = await repo.get_comment_by_id(db, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise CommentNotFoundError()
    if not is_admin and comment.user_id != requesting_user_id:
        raise CommentForbiddenError()
    await repo.soft_delete_comment(db, comment)
    await db.commit()
