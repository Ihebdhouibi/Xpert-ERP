"""Time entry and comment endpoints for repair orders."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.models import AppUser
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.repair_order.models import RepairOrder
from .time_entry_schemas import (
    CommentCreateRequest,
    CommentListResponse,
    CommentSummary,
    CommentUpdateRequest,
    TimeEntryListResponse,
    TimeEntryStartRequest,
    TimeEntrySummary,
    TimeEntryStopRequest,
)
from . import time_entry_service as svc
from app.core.logging import get_logger

router = APIRouter(tags=["repair-order-time-comments"])
logger = get_logger("repair_order.time_entry_router")


async def _resolve_user_id(db: AsyncSession, public_id: str) -> int:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid user identity")
    result = await db.execute(select(AppUser.id).where(AppUser.public_id == uid))
    row = result.first()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return row[0]


async def _resolve_ro_id(db: AsyncSession, garage_id: int, public_id: str) -> int:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Repair order not found")
    result = await db.execute(
        select(RepairOrder.id).where(
            RepairOrder.public_id == uid,
            RepairOrder.garage_id == garage_id,
            RepairOrder.deleted_at.is_(None),
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Repair order not found")
    return row[0]


# ---------------------------------------------------------------------------
# Time Entry endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/time-entries/start",
    response_model=TimeEntrySummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("repair_order.update")],
)
async def start_time_entry(
    public_id: str,
    body: TimeEntryStartRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> TimeEntrySummary:
    ro_id = await _resolve_ro_id(db, user.garage_id, public_id)
    user_id = await _resolve_user_id(db, user.public_id)
    try:
        entry = await svc.start_time_entry(db, ro_id, user_id, body.notes)
    except svc.TimeEntryAlreadyOpenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "time_entry_already_open"},
        )
    return TimeEntrySummary.model_validate(entry)


@router.post(
    "/{public_id}/time-entries/stop",
    response_model=TimeEntrySummary,
    dependencies=[require_permission("repair_order.update")],
)
async def stop_time_entry(
    public_id: str,
    body: TimeEntryStopRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> TimeEntrySummary:
    ro_id = await _resolve_ro_id(db, user.garage_id, public_id)
    user_id = await _resolve_user_id(db, user.public_id)
    try:
        entry = await svc.stop_time_entry(db, ro_id, user_id, body.notes)
    except svc.TimeEntryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "no_open_time_entry"},
        )
    return TimeEntrySummary.model_validate(entry)


@router.get(
    "/{public_id}/time-entries",
    response_model=TimeEntryListResponse,
    dependencies=[require_permission("repair_order.read")],
)
async def list_time_entries(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> TimeEntryListResponse:
    ro_id = await _resolve_ro_id(db, user.garage_id, public_id)
    entries = await svc.list_time_entries(db, ro_id)
    return TimeEntryListResponse(
        items=[TimeEntrySummary.model_validate(e) for e in entries],
        total=len(entries),
    )


# ---------------------------------------------------------------------------
# Comment endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/comments",
    response_model=CommentSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("repair_order.read")],
)
async def create_comment(
    public_id: str,
    body: CommentCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CommentSummary:
    ro_id = await _resolve_ro_id(db, user.garage_id, public_id)
    user_id = await _resolve_user_id(db, user.public_id)
    comment = await svc.create_comment(db, ro_id, user_id, body.body)
    return CommentSummary.model_validate(comment)


@router.get(
    "/{public_id}/comments",
    response_model=CommentListResponse,
    dependencies=[require_permission("repair_order.read")],
)
async def list_comments(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    ro_id = await _resolve_ro_id(db, user.garage_id, public_id)
    comments = await svc.list_comments(db, ro_id)
    return CommentListResponse(
        items=[CommentSummary.model_validate(c) for c in comments],
        total=len(comments),
    )


@router.put(
    "/{public_id}/comments/{comment_id}",
    response_model=CommentSummary,
    dependencies=[require_permission("repair_order.read")],
)
async def update_comment(
    public_id: str,
    comment_id: int,
    body: CommentUpdateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CommentSummary:
    user_id = await _resolve_user_id(db, user.public_id)
    try:
        comment = await svc.update_comment(db, comment_id, user_id, body.body)
    except svc.CommentNotFoundError:
        raise HTTPException(status_code=404, detail="Comment not found")
    except svc.CommentForbiddenError:
        raise HTTPException(status_code=403, detail="Cannot edit another user's comment")
    return CommentSummary.model_validate(comment)


@router.delete(
    "/{public_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("repair_order.read")],
)
async def delete_comment(
    public_id: str,
    comment_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    user_id = await _resolve_user_id(db, user.public_id)
    is_admin = user.has_permission("repair_order.delete")
    try:
        await svc.delete_comment(db, comment_id, user_id, is_admin)
    except svc.CommentNotFoundError:
        raise HTTPException(status_code=404, detail="Comment not found")
    except svc.CommentForbiddenError:
        raise HTTPException(status_code=403, detail="Cannot delete another user's comment")
