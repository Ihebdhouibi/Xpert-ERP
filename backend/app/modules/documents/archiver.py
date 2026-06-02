"""APScheduler job: move old GED documents to archive storage daily."""
from __future__ import annotations

import logging

from app.core.database import AsyncSessionFactory
from app.modules.documents import service

logger = logging.getLogger(__name__)


async def _run_document_archive() -> None:
    async with AsyncSessionFactory() as db:
        try:
            archived = await service.archive_old_documents(db)
            if archived:
                logger.info("document_archive_job_done", archived=archived)
        except Exception:
            logger.exception("document_archive_job_error")
            await db.rollback()


def register_document_archiver_job(scheduler) -> None:  # type: ignore[no-untyped-def]
    """Add the daily document archive job to an existing APScheduler instance."""
    scheduler.add_job(
        _run_document_archive,
        trigger="interval",
        hours=24,
        id="document_archive",
        max_instances=1,
        coalesce=True,
    )
