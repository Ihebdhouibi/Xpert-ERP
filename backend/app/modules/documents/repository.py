"""Document repository — thin DB access layer."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, select, text, update
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


async def list_documents(
    db: AsyncSession,
    *,
    garage_id: int,
    category: Optional[DocumentCategory] = None,
    owner_entity_type: Optional[OwnerEntityType] = None,
    owner_entity_id: Optional[int] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    """Return active documents matching filters.  ``q`` triggers FTS on filename + extracted_text."""
    filters = [
        Document.garage_id == garage_id,
        Document.status == DocumentStatus.active,
    ]
    if category is not None:
        filters.append(Document.category == category)
    if owner_entity_type is not None:
        filters.append(Document.owner_entity_type == owner_entity_type)
    if owner_entity_id is not None:
        filters.append(Document.owner_entity_id == owner_entity_id)
    if from_date is not None:
        filters.append(Document.uploaded_at >= from_date)
    if to_date is not None:
        filters.append(Document.uploaded_at <= to_date)
    if q:
        # Use plainto_tsquery for safe, injection-free FTS
        fts_expr = text(
            "to_tsvector('french', coalesce(document.filename, '') || ' ' || coalesce(document.extracted_text, '')) "
            "@@ plainto_tsquery('french', :q)"
        ).bindparams(q=q)
        filters.append(fts_expr)

    stmt = (
        select(Document)
        .where(and_(*filters))
        .order_by(Document.uploaded_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def soft_delete(
    db: AsyncSession,
    *,
    public_id: uuid.UUID,
    garage_id: int,
) -> Document | None:
    """Soft-delete a document; returns the updated row or None if not found."""
    doc = await get_by_public_id(db, public_id=public_id, garage_id=garage_id)
    if doc is None:
        return None
    doc.status = DocumentStatus.deleted
    await db.commit()
    await db.refresh(doc)
    return doc


async def get_archivable_documents(
    db: AsyncSession,
    *,
    garage_id: int,
    older_than: datetime,
) -> list[Document]:
    """Return active, non-archived documents uploaded before *older_than*."""
    result = await db.execute(
        select(Document).where(
            Document.garage_id == garage_id,
            Document.status == DocumentStatus.active,
            Document.archived.is_(False),
            Document.uploaded_at < older_than,
        )
    )
    return list(result.scalars().all())


async def mark_archived(
    db: AsyncSession,
    *,
    document_id: int,
    archived_at: datetime,
) -> None:
    """Mark a single document as archived."""
    await db.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(archived=True, archived_at=archived_at)
    )


async def get_all_garage_ids(db: AsyncSession) -> list[int]:
    """Return distinct garage IDs that have at least one document — for scheduler."""
    result = await db.execute(
        select(Document.garage_id).distinct()
    )
    return list(result.scalars().all())
