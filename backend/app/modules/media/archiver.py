"""APScheduler job: move old inspection media to cold storage daily."""
from __future__ import annotations

import logging

from app.core.database import AsyncSessionFactory
from app.modules.media import service

logger = logging.getLogger(__name__)


async def _run_media_archive() -> None:
    async with AsyncSessionFactory() as db:
        try:
            archived = await service.archive_old_media(db)
            await db.commit()
            if archived:
                logger.info("media_archive_job_done", archived=archived)
        except Exception:
            logger.exception("media_archive_job_error")
            await db.rollback()


def register_archiver_job(scheduler) -> None:  # type: ignore[no-untyped-def]
    """Add the daily media archive job to an existing APScheduler instance."""
    scheduler.add_job(
        _run_media_archive,
        trigger="interval",
        hours=24,
        id="media_archive",
        max_instances=1,
        coalesce=True,
    )
