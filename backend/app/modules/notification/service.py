"""
Notification dispatch service.

Handles:
- DB-first template loading (Jinja2 from_string), with filesystem fallback
- Quiet-hours enforcement (delays the coroutine until the window ends)
- Exponential-backoff retry up to CFG_NOTIFICATION_MAX_RETRIES
- Persistent notification_log tracking (queued → sent | failed)

Meant to be invoked via FastAPI BackgroundTasks or the APScheduler jobs so
that the HTTP response is not blocked by the sleep delays.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.notification.adapter import (
    DeliveryResult,
    EmailAdapter,
    EmailAttachment,
    NotificationAdapter,
    SmsAdapter,
)
from app.modules.notification.models import NotificationChannel, NotificationStatus
from app.modules.notification.repository import NotificationRepository, TemplateRepository

logger = get_logger("notification.service")

_FS_TEMPLATES_DIR = Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class NotificationChannelError(Exception):
    pass


# ---------------------------------------------------------------------------
# Quiet-hours helpers
# ---------------------------------------------------------------------------


def _parse_hhmm(value: str) -> dt_time:
    h, m = value.split(":", 1)
    return dt_time(int(h), int(m))


def _in_quiet_hours(now: datetime, start: dt_time, end: dt_time) -> bool:
    t = dt_time(now.hour, now.minute)
    if start > end:
        return t >= start or t < end
    return start <= t < end


def _seconds_until_quiet_end(now: datetime, end: dt_time) -> float:
    target = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max((target - now).total_seconds(), 0.0)


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------


def _get_adapter(channel: str) -> NotificationAdapter:
    if channel == NotificationChannel.email:
        return EmailAdapter()
    if channel == NotificationChannel.sms:
        return SmsAdapter()
    raise NotificationChannelError(f"unknown channel: {channel!r}")


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


async def _render_template(
    db: AsyncSession,
    garage_id: int,
    template_code: str,
    channel: str,
    context: dict[str, Any],
    locale: str = "fr",
) -> tuple[Optional[str], str]:
    """Return (subject, rendered_body) for the given template.

    Loads from DB first; falls back to filesystem templates if not found in DB.
    """
    tmpl = await TemplateRepository.get_active(db, garage_id, template_code, channel, locale)
    if tmpl:
        autoescape = channel == NotificationChannel.email
        env = Environment(autoescape=autoescape)
        body = env.from_string(tmpl.body).render(**context)
        subject: Optional[str] = None
        if tmpl.subject:
            subject = env.from_string(tmpl.subject).render(**context)
        return subject, body

    # Filesystem fallback (legacy templates in notification/templates/)
    subdir = "email" if channel == NotificationChannel.email else "sms"
    ext = "html" if channel == NotificationChannel.email else "txt"
    fs_env = Environment(
        loader=FileSystemLoader(str(_FS_TEMPLATES_DIR / subdir)),
        autoescape=(channel == NotificationChannel.email),
    )
    try:
        fs_tmpl = fs_env.get_template(f"{template_code}.{ext}")
        body = fs_tmpl.render(**context)
        subject = context.get("subject")  # type: ignore[assignment]
        return subject, body
    except TemplateNotFound:
        logger.warning(
            "notification_template_not_found",
            template_code=template_code,
            channel=channel,
        )
        return template_code, str(context)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def dispatch(
    db: AsyncSession,
    *,
    garage_id: int,
    recipient_id: Optional[int],
    recipient: str,
    channel: str,
    template_code: str,
    context: dict[str, Any],
    locale: str = "fr",
    attachments: Optional[list[EmailAttachment]] = None,
    respect_quiet_hours: bool = True,
) -> None:
    """Send a notification with retry and quiet-hours support.

    Creates a notification_log row immediately (status=queued), then
    attempts delivery up to CFG_NOTIFICATION_MAX_RETRIES times with
    exponential backoff. Final status is always persisted.

    Call this from a FastAPI BackgroundTask or APScheduler job. For
    manually-triggered sends (a user clicking "send"), pass
    respect_quiet_hours=False so the request doesn't block for hours.
    """
    logger.info("dispatch_start", garage_id=garage_id, channel=channel, template_code=template_code)
    settings = get_settings()
    max_retries: int = settings.cfg_notification_max_retries
    quiet_start = _parse_hhmm(settings.cfg_quiet_hours_start)
    quiet_end = _parse_hhmm(settings.cfg_quiet_hours_end)

    log = await NotificationRepository.create(
        db,
        garage_id=garage_id,
        recipient_id=recipient_id,
        channel=channel,
        template_code=template_code,
    )
    await db.commit()

    # Delay if inside quiet hours
    now = datetime.now(tz=timezone.utc)
    if respect_quiet_hours and _in_quiet_hours(now, quiet_start, quiet_end):
        wait = _seconds_until_quiet_end(now, quiet_end)
        logger.info("notification_quiet_hours_delay", log_id=log.id, wait_seconds=round(wait))
        await asyncio.sleep(wait)

    subject, body = await _render_template(db, garage_id, template_code, channel, context, locale)

    adapter = _get_adapter(channel)
    delay = 1.0
    result: Optional[DeliveryResult] = None

    for attempt in range(1, max_retries + 1):
        try:
            result = await adapter.send(recipient, channel, subject, body, attachments=attachments)
        except Exception as exc:
            result = DeliveryResult(success=False, error=type(exc).__name__)

        await NotificationRepository.increment_attempt(db, log.id)
        await db.commit()

        if result.success:
            await NotificationRepository.mark_sent(db, log.id, result.provider_reference)
            await db.commit()
            logger.info(
                "notification_sent",
                log_id=log.id,
                channel=channel,
                template_code=template_code,
                attempt=attempt,
            )
            return

        logger.warning(
            "notification_attempt_failed",
            log_id=log.id,
            attempt=attempt,
            max_retries=max_retries,
            error=result.error,
        )

        if attempt < max_retries:
            await asyncio.sleep(delay)
            delay *= 2

    error_detail = result.error if result else "unknown"
    await NotificationRepository.mark_failed(db, log.id, error_detail=error_detail)
    await db.commit()
    logger.error(
        "notification_failed_permanently",
        log_id=log.id,
        channel=channel,
        template_code=template_code,
        attempts=max_retries,
    )


def get_admin_recipients() -> list[str]:
    """Parse the comma-separated CFG_ADMIN_NOTIFICATION_EMAILS setting."""
    raw = get_settings().cfg_admin_notification_emails
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


async def render_preview(
    db: AsyncSession,
    *,
    garage_id: int,
    template_id: int,
    context: dict[str, Any],
) -> tuple[Optional[str], str]:
    """Render a template by ID with the given context for admin preview."""
    tmpl = await TemplateRepository.get_by_id(db, template_id, garage_id)
    if not tmpl:
        return None, ""
    autoescape = tmpl.channel == NotificationChannel.email
    env = Environment(autoescape=autoescape)
    body = env.from_string(tmpl.body).render(**context)
    subject: Optional[str] = None
    if tmpl.subject:
        subject = env.from_string(tmpl.subject).render(**context)
    return subject, body
