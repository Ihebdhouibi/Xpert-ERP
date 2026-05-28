"""
APScheduler jobs for scheduled notification triggers.

Jobs run every minute (interval=1 min) and fire dispatches when due.
Each job uses its own DB session opened from AsyncSessionFactory.

Deduplication: before dispatching, we check notification_log to ensure
this recipient hasn't already received the same template in the last
(delay_days - 1) days, preventing re-sends on every scheduler tick.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.modules.notification.repository import NotificationRepository
from app.modules.notification.service import dispatch

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _dispatch_if_not_sent(
    db: AsyncSession,
    *,
    garage_id: int,
    recipient_id: int,
    recipient_email: Optional[str],
    recipient_phone: Optional[str],
    template_code: str,
    context: dict,
    dedup_window_days: int,
) -> None:
    """Dispatch email + sms for recipient, skipping if already sent within the dedup window."""
    since = datetime.now(tz=timezone.utc) - timedelta(days=max(dedup_window_days - 1, 1))

    already_sent = await NotificationRepository.has_recent(db, recipient_id, template_code, since)
    if already_sent:
        return

    if recipient_email:
        await dispatch(
            db,
            garage_id=garage_id,
            recipient_id=recipient_id,
            recipient=recipient_email,
            channel="email",
            template_code=template_code,
            context=context,
        )
    if recipient_phone:
        await dispatch(
            db,
            garage_id=garage_id,
            recipient_id=recipient_id,
            recipient=recipient_phone,
            channel="sms",
            template_code=template_code,
            context=context,
        )


# ---------------------------------------------------------------------------
# Job: unpaid invoice reminders (3 levels)
# ---------------------------------------------------------------------------


async def _run_invoice_reminders() -> None:
    settings = get_settings()
    levels = [
        (settings.cfg_reminder_delay_1_days, "unpaid_invoice_reminder_1"),
        (settings.cfg_reminder_delay_2_days, "unpaid_invoice_reminder_2"),
        (settings.cfg_reminder_delay_3_days, "unpaid_invoice_reminder_3"),
    ]
    now = datetime.now(tz=timezone.utc)

    async with AsyncSessionFactory() as db:
        try:
            from app.modules.invoice.models import Invoice, InvoiceStatus
            from app.modules.customer.models import Customer

            for delay_days, template_code in levels:
                threshold = now - timedelta(days=delay_days)
                # Invoices overdue by exactly delay_days (±1 day window to avoid missing ticks)
                window_start = threshold - timedelta(days=1)
                result = await db.execute(
                    select(Invoice, Customer)
                    .join(Customer, Customer.id == Invoice.customer_id)
                    .where(
                        Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partial]),
                        Invoice.due_at <= threshold,
                        Invoice.due_at > window_start,
                        Invoice.deleted_at.is_(None),
                        Customer.email.isnot(None),
                    )
                )
                rows = result.all()
                for invoice, customer in rows:
                    context = {
                        "customer_name": customer.full_name,
                        "invoice_number": invoice.doc_number or str(invoice.id),
                        "amount_due": f"{invoice.outstanding_minor / 100:.2f}",
                        "due_date": invoice.due_at.strftime("%Y-%m-%d") if invoice.due_at else "",
                        "garage_name": settings.pdf_garage_name,
                        "garage_phone": settings.pdf_garage_phone,
                    }
                    await _dispatch_if_not_sent(
                        db,
                        garage_id=invoice.garage_id,
                        recipient_id=customer.id,
                        recipient_email=customer.email,
                        recipient_phone=customer.phone_e164,
                        template_code=template_code,
                        context=context,
                        dedup_window_days=delay_days,
                    )
        except Exception:
            logger.exception("scheduler_invoice_reminders_error")
            await db.rollback()


# ---------------------------------------------------------------------------
# Job: maintenance due
# ---------------------------------------------------------------------------


async def _run_maintenance_due() -> None:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    # Notify when maintenance is due in the next 7 days
    lookahead_days = 7
    window_end = now + timedelta(days=lookahead_days)

    async with AsyncSessionFactory() as db:
        try:
            from app.modules.vehicles.models import Vehicle, VehicleStatus
            from app.modules.customer.models import Customer

            result = await db.execute(
                select(Vehicle, Customer)
                .join(Customer, Customer.id == Vehicle.customer_id)
                .where(
                    Vehicle.maintenance_due_at.isnot(None),
                    Vehicle.maintenance_due_at >= now,
                    Vehicle.maintenance_due_at <= window_end,
                    Vehicle.status == VehicleStatus.active,
                    Vehicle.deleted_at.is_(None),
                    Customer.email.isnot(None),
                )
            )
            for vehicle, customer in result.all():
                context = {
                    "customer_name": customer.full_name,
                    "vehicle": f"{vehicle.make} {vehicle.model} {vehicle.year or ''}".strip(),
                    "registration": vehicle.registration or vehicle.vin or "",
                    "due_date": vehicle.maintenance_due_at.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
                    "garage_name": settings.pdf_garage_name,
                    "garage_phone": settings.pdf_garage_phone,
                }
                await _dispatch_if_not_sent(
                    db,
                    garage_id=vehicle.garage_id,
                    recipient_id=customer.id,
                    recipient_email=customer.email,
                    recipient_phone=customer.phone_e164,
                    template_code="maintenance_due",
                    context=context,
                    dedup_window_days=lookahead_days,
                )
        except Exception:
            logger.exception("scheduler_maintenance_due_error")
            await db.rollback()


# ---------------------------------------------------------------------------
# Job: technical inspection due
# ---------------------------------------------------------------------------


async def _run_technical_inspection_due() -> None:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    lookahead_days = 30
    window_end = now + timedelta(days=lookahead_days)

    async with AsyncSessionFactory() as db:
        try:
            from app.modules.vehicles.models import Vehicle, VehicleStatus
            from app.modules.customer.models import Customer

            result = await db.execute(
                select(Vehicle, Customer)
                .join(Customer, Customer.id == Vehicle.customer_id)
                .where(
                    Vehicle.technical_inspection_due_at.isnot(None),
                    Vehicle.technical_inspection_due_at >= now,
                    Vehicle.technical_inspection_due_at <= window_end,
                    Vehicle.status == VehicleStatus.active,
                    Vehicle.deleted_at.is_(None),
                    Customer.email.isnot(None),
                )
            )
            for vehicle, customer in result.all():
                context = {
                    "customer_name": customer.full_name,
                    "vehicle": f"{vehicle.make} {vehicle.model} {vehicle.year or ''}".strip(),
                    "registration": vehicle.registration or vehicle.vin or "",
                    "due_date": vehicle.technical_inspection_due_at.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
                    "garage_name": settings.pdf_garage_name,
                    "garage_phone": settings.pdf_garage_phone,
                }
                await _dispatch_if_not_sent(
                    db,
                    garage_id=vehicle.garage_id,
                    recipient_id=customer.id,
                    recipient_email=customer.email,
                    recipient_phone=customer.phone_e164,
                    template_code="technical_inspection_due",
                    context=context,
                    dedup_window_days=lookahead_days,
                )
        except Exception:
            logger.exception("scheduler_technical_inspection_error")
            await db.rollback()


# ---------------------------------------------------------------------------
# Job: quotation expiring
# ---------------------------------------------------------------------------


async def _run_quotation_expiring() -> None:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    lookahead_days = 3
    window_end = now + timedelta(days=lookahead_days)

    async with AsyncSessionFactory() as db:
        try:
            from app.modules.quotation.models import Quotation, QuotationStatus
            from app.modules.customer.models import Customer

            result = await db.execute(
                select(Quotation, Customer)
                .join(Customer, Customer.id == Quotation.customer_id)
                .where(
                    Quotation.status == QuotationStatus.sent,
                    Quotation.valid_until.isnot(None),
                    Quotation.valid_until >= now,
                    Quotation.valid_until <= window_end,
                    Quotation.deleted_at.is_(None),
                    Customer.email.isnot(None),
                )
            )
            for quotation, customer in result.all():
                context = {
                    "customer_name": customer.full_name,
                    "quotation_number": quotation.doc_number or str(quotation.id),
                    "total": f"{quotation.total_minor / 100:.2f}",
                    "expires_at": quotation.valid_until.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
                    "garage_name": settings.pdf_garage_name,
                    "garage_phone": settings.pdf_garage_phone,
                }
                await _dispatch_if_not_sent(
                    db,
                    garage_id=quotation.garage_id,
                    recipient_id=customer.id,
                    recipient_email=customer.email,
                    recipient_phone=customer.phone_e164,
                    template_code="quotation_expiring",
                    context=context,
                    dedup_window_days=lookahead_days,
                )
        except Exception:
            logger.exception("scheduler_quotation_expiring_error")
            await db.rollback()


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------


def configure_scheduler() -> AsyncIOScheduler:
    """Register all notification jobs and return the configured scheduler."""
    scheduler.add_job(
        _run_invoice_reminders,
        trigger="interval",
        minutes=1,
        id="invoice_reminders",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_maintenance_due,
        trigger="interval",
        minutes=1,
        id="maintenance_due",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_technical_inspection_due,
        trigger="interval",
        minutes=1,
        id="technical_inspection_due",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_quotation_expiring,
        trigger="interval",
        minutes=1,
        id="quotation_expiring",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
