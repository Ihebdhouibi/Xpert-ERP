"""OCR extraction DB access layer."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ocr.models import OcrExtraction, OcrStatus


async def create(
    db: AsyncSession,
    *,
    document_id: int,
) -> OcrExtraction:
    row = OcrExtraction(
        public_id=uuid.uuid4(),
        document_id=document_id,
        status=OcrStatus.pending,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_by_public_id(
    db: AsyncSession, *, public_id: uuid.UUID
) -> Optional[OcrExtraction]:
    result = await db.execute(
        select(OcrExtraction).where(OcrExtraction.public_id == public_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(
    db: AsyncSession, *, extraction_id: int
) -> Optional[OcrExtraction]:
    result = await db.execute(
        select(OcrExtraction).where(OcrExtraction.id == extraction_id)
    )
    return result.scalar_one_or_none()


async def get_pending(db: AsyncSession) -> list[OcrExtraction]:
    result = await db.execute(
        select(OcrExtraction).where(OcrExtraction.status == OcrStatus.pending)
    )
    return list(result.scalars().all())


async def update_status(
    db: AsyncSession,
    *,
    extraction_id: int,
    status: OcrStatus,
    raw_text: Optional[str] = None,
    structured_fields: Optional[dict[str, Any]] = None,
    confidence_scores: Optional[dict[str, float]] = None,
    processed_at: Optional[datetime] = None,
) -> None:
    values: dict[str, Any] = {"status": status}
    if raw_text is not None:
        values["raw_text"] = raw_text
    if structured_fields is not None:
        values["structured_fields"] = structured_fields
    if confidence_scores is not None:
        values["confidence_scores"] = confidence_scores
    if processed_at is not None:
        values["processed_at"] = processed_at
    await db.execute(
        update(OcrExtraction)
        .where(OcrExtraction.id == extraction_id)
        .values(**values)
    )
    await db.commit()


async def mark_reviewed(
    db: AsyncSession,
    *,
    extraction_id: int,
    reviewed_by: int,
    reviewed_at: datetime,
) -> None:
    await db.execute(
        update(OcrExtraction)
        .where(OcrExtraction.id == extraction_id)
        .values(
            status=OcrStatus.completed,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
        )
    )
    await db.commit()
