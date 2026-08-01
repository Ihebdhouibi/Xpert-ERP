"""In-app notification inbox — /notifications endpoints (bell)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.notification.models import AppNotification
from app.modules.rbac.dependencies import AuthUser

router = APIRouter(prefix="/notifications", tags=["notifications"])

_LINK_PATTERN = re.compile(r"^/(invoices|customers)/([^/]+)$")


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


class NotificationHistoryResponse(BaseModel):
    items: list[AppNotificationOut]
    total: int
    page: int
    page_size: int
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
            .limit(10)
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


@router.get("/history", response_model=NotificationHistoryResponse)
async def list_notification_history(
    user: AuthUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> NotificationHistoryResponse:
    """Full, paginated notification history for the /notifications page."""
    filters = [AppNotification.recipient_id == user.user_id]
    if unread_only:
        filters.append(AppNotification.read_at.is_(None))

    total = (
        await db.execute(
            select(func.count()).select_from(AppNotification).where(*filters)
        )
    ).scalar_one()
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
    rows = (
        await db.execute(
            select(AppNotification)
            .where(*filters)
            .order_by(AppNotification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return NotificationHistoryResponse(
        items=[AppNotificationOut.model_validate(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
        unread_count=int(unread),
    )


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
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
    return {"status": "read"}


@router.post("/{notification_id}/send-email")
async def send_notification_email(
    notification_id: int,
    user: AuthUser,
    recipient: Literal["client", "admin"] = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Email the client or admin about the underlying échéance / credit-limit alert.

    Only supports notifications whose link points at an invoice (échéance)
    or a customer (credit-limit) — the only two triggers that currently
    expose this action in the bell dropdown.
    """
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

    match = _LINK_PATTERN.match(notif.link or "")
    if not match:
        raise HTTPException(status_code=422, detail="Cette notification ne peut pas être envoyée par email.")

    resource, public_id = match.group(1), match.group(2)

    if resource == "invoices":
        from app.modules.invoice import service as invoice_service

        try:
            inv = await invoice_service._resolve(db, public_id, user.garage_id)
            await invoice_service.send_invoice_due_alert_email(
                db, inv.id, user.garage_id, recipient=recipient
            )
        except invoice_service.InvoiceNotFoundError:
            raise HTTPException(status_code=404, detail="Invoice not found")
        except invoice_service.InvoiceStateError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:  # customers
        from app.modules.customer import repository as customer_repo
        from app.modules.customer.credit_service import CreditAlertError, send_credit_limit_alert_email

        customer = await customer_repo.get_by_public_id(db, user.garage_id, public_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        try:
            await send_credit_limit_alert_email(db, customer.id, user.garage_id, recipient=recipient)
        except CreditAlertError as e:
            raise HTTPException(status_code=422, detail=str(e))

    return {"status": "sent"}


@router.post("/read-all")
async def mark_all_read(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await db.execute(
        update(AppNotification)
        .where(
            AppNotification.recipient_id == user.user_id,
            AppNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(tz=timezone.utc))
    )
    await db.commit()
    return {"status": "ok"}
