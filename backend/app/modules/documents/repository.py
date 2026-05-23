"""Document repository — thin DB access layer."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentCategory, DocumentStatus, OwnerEntityType


async def create_document(
    db: AsyncSession,
    *,
    garage_id: int,
    owner_entity_type: OwnerEntityType,
    owner_entity_id: int | None,
    category: DocumentCategory,
    filename: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
    storage_key: str,
    uploaded_by: int,
) -> Document:
    doc = Document(
        public_id=uuid.uuid4(),
        garage_id=garage_id,
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        category=category,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
        storage_key=storage_key,
        uploaded_by=uploaded_by,
        uploaded_at=datetime.now(tz=timezone.utc),
        status=DocumentStatus.active,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def get_by_public_id(
    db: AsyncSession,
    *,
    public_id: uuid.UUID,
    garage_id: int,
) -> Document | None:
    result = await db.execute(
        select(Document).where(
            Document.public_id == public_id,
            Document.garage_id == garage_id,
            Document.status == DocumentStatus.active,
        )
    )
    return result.scalar_one_or_none()
