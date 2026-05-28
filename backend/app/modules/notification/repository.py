from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notification.models import NotificationLog, NotificationStatus, NotificationTemplate


class NotificationRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        garage_id: int,
        recipient_id: Optional[int],
        channel: str,
        template_code: str,
    ) -> NotificationLog:
        log = NotificationLog(
            garage_id=garage_id,
            recipient_id=recipient_id,
            channel=channel,
            template_code=template_code,
            status=NotificationStatus.queued,
            attempts=0,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log

    @staticmethod
    async def get(db: AsyncSession, log_id: int) -> Optional[NotificationLog]:
        result = await db.execute(
            select(NotificationLog).where(NotificationLog.id == log_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        recipient_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NotificationLog], int]:
        base = select(NotificationLog).where(NotificationLog.garage_id == garage_id)
        if status is not None:
            base = base.where(NotificationLog.status == status)
        if channel is not None:
            base = base.where(NotificationLog.channel == channel)
        if recipient_id is not None:
            base = base.where(NotificationLog.recipient_id == recipient_id)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_q)).scalar_one()

        items_q = (
            base.order_by(NotificationLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await db.execute(items_q)
        return list(rows.scalars().all()), total

    @staticmethod
    async def increment_attempt(db: AsyncSession, log_id: int) -> None:
        await db.execute(
            update(NotificationLog)
            .where(NotificationLog.id == log_id)
            .values(attempts=NotificationLog.attempts + 1)
        )
        await db.flush()

    @staticmethod
    async def mark_sent(
        db: AsyncSession,
        log_id: int,
        provider_reference: Optional[str],
    ) -> None:
        await db.execute(
            update(NotificationLog)
            .where(NotificationLog.id == log_id)
            .values(
                status=NotificationStatus.sent,
                provider_reference=provider_reference,
                sent_at=datetime.now(tz=timezone.utc),
            )
        )
        await db.flush()

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        log_id: int,
        error_detail: str,
    ) -> None:
        await db.execute(
            update(NotificationLog)
            .where(NotificationLog.id == log_id)
            .values(
                status=NotificationStatus.failed,
                error_detail=error_detail,
            )
        )
        await db.flush()

    @staticmethod
    async def has_recent(
        db: AsyncSession,
        recipient_id: int,
        template_code: str,
        since: datetime,
    ) -> bool:
        """Return True if a notification was already sent/queued for this recipient+code since *since*."""
        result = await db.execute(
            select(NotificationLog.id)
            .where(
                NotificationLog.recipient_id == recipient_id,
                NotificationLog.template_code == template_code,
                NotificationLog.status.in_([NotificationStatus.sent, NotificationStatus.queued]),
                NotificationLog.created_at >= since,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def mark_bounced(
        db: AsyncSession,
        log_id: int,
        error_detail: Optional[str] = None,
    ) -> None:
        await db.execute(
            update(NotificationLog)
            .where(NotificationLog.id == log_id)
            .values(
                status=NotificationStatus.bounced,
                error_detail=error_detail,
            )
        )
        await db.flush()


class TemplateRepository:
    @staticmethod
    async def get_active(
        db: AsyncSession,
        garage_id: int,
        code: str,
        channel: str,
        locale: str = "fr",
    ) -> Optional[NotificationTemplate]:
        """Return garage-specific template, falling back to the system default (garage_id=0)."""
        result = await db.execute(
            select(NotificationTemplate)
            .where(
                or_(
                    NotificationTemplate.garage_id == garage_id,
                    NotificationTemplate.garage_id == 0,
                ),
                NotificationTemplate.code == code,
                NotificationTemplate.channel == channel,
                NotificationTemplate.locale == locale,
                NotificationTemplate.active.is_(True),
            )
            .order_by(NotificationTemplate.garage_id.desc())  # garage-specific wins
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_admin(
        db: AsyncSession,
        garage_id: int,
    ) -> list[NotificationTemplate]:
        """List all system templates merged with garage overrides."""
        result = await db.execute(
            select(NotificationTemplate)
            .where(
                or_(
                    NotificationTemplate.garage_id == garage_id,
                    NotificationTemplate.garage_id == 0,
                )
            )
            .order_by(NotificationTemplate.code, NotificationTemplate.channel, NotificationTemplate.garage_id.desc())
        )
        rows = list(result.scalars().all())
        # Deduplicate: if a garage override exists, drop the system default for same key
        seen: set[tuple[str, str, str]] = set()
        deduplicated: list[NotificationTemplate] = []
        for tmpl in rows:
            key = (tmpl.code, tmpl.channel, tmpl.locale)
            if key not in seen:
                seen.add(key)
                deduplicated.append(tmpl)
        return deduplicated

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        template_id: int,
        garage_id: int,
    ) -> Optional[NotificationTemplate]:
        """Fetch a single template visible to this garage (own or system)."""
        result = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.id == template_id,
                or_(
                    NotificationTemplate.garage_id == garage_id,
                    NotificationTemplate.garage_id == 0,
                ),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        *,
        garage_id: int,
        code: str,
        channel: str,
        locale: str,
        subject: Optional[str],
        body: str,
        active: bool = True,
    ) -> NotificationTemplate:
        """Create or update a template (matched on garage_id+code+channel+locale)."""
        result = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.garage_id == garage_id,
                NotificationTemplate.code == code,
                NotificationTemplate.channel == channel,
                NotificationTemplate.locale == locale,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.subject = subject
            existing.body = body
            existing.active = active
            existing.updated_at = datetime.now(tz=timezone.utc)
            await db.flush()
            return existing
        tmpl = NotificationTemplate(
            garage_id=garage_id,
            code=code,
            channel=channel,
            locale=locale,
            subject=subject,
            body=body,
            active=active,
        )
        db.add(tmpl)
        await db.flush()
        await db.refresh(tmpl)
        return tmpl
