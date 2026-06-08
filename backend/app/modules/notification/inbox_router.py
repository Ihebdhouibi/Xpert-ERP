"""In-app notification inbox — /notifications endpoints (bell)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.notification.models import AppNotification
from app.modules.rbac.dependencies import AuthUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


class AppNotificationOut(BaseModel):
    id: int
    title: str
    body: Optional[str]
    link: Optional[str]
    read_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class InboxResponse(BaseModel):
    items: list[AppNotificationOut]
    unread_count: int


async def create_app_notification(
    db: AsyncSession,
    *,
    garage_id: int,
    recipient_id: int,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
) -> AppNotification:
    """Create an in-app notification for a user (caller commits)."""
    notif = AppNotification(
        garage_id=garage_id,
        recipient_id=recipient_id,
        title=title,
        body=body,
        link=link,
    )
    db.add(notif)
    await db.flush()
    return notif


@router.get("", response_model=InboxResponse)
async def list_my_notifications(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InboxResponse:
    """List the current user's most recent notifications + unread count."""
    rows = (
        await db.execute(
            select(AppNotification)
            .where(AppNotification.recipient_id == user.user_id)
            .order_by(AppNotification.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    unread = (
        await db.execute(
            select(func.count())
            .select_from(AppNotification)
            .where(
                AppNotification.recipient_id == user.user_id,
                AppNotification.read_at.is_(None),
            )
        )
    ).scalar_one()
    return InboxResponse(
        items=[AppNotificationOut.model_validate(r) for r in rows],
        unread_count=int(unread),
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    notif = (
        await db.execute(
            select(AppNotification).where(
                AppNotification.id == notification_id,
                AppNotification.recipient_id == user.user_id,
            )
        )
    ).scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.read_at is None:
        notif.read_at = datetime.now(tz=timezone.utc)
        await db.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(
        update(AppNotification)
        .where(
            AppNotification.recipient_id == user.user_id,
            AppNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(tz=timezone.utc))
    )
    await db.commit()
