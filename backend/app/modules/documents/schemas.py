"""Pydantic schemas for the document module.

IMPORTANT: storage_key is intentionally absent from all response schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.modules.documents.models import DocumentCategory, DocumentStatus, OwnerEntityType


class DocumentOut(BaseModel):
    """Public document representation — no internal storage path."""

    id: str = Field(description="Public UUID of the document")
    garage_id: int
    owner_entity_type: OwnerEntityType
    owner_entity_id: int | None
    category: DocumentCategory
    filename: str
    mime_type: str
    size_bytes: int
    uploaded_by: int
    uploaded_at: datetime
    status: DocumentStatus
    archived: bool
    archived_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, doc: object) -> "DocumentOut":
        from app.modules.documents.models import Document

        d: Document = doc  # type: ignore[assignment]
        return cls(
            id=str(d.public_id),
            garage_id=d.garage_id,
            owner_entity_type=d.owner_entity_type,  # type: ignore[arg-type]
            owner_entity_id=d.owner_entity_id,
            category=d.category,  # type: ignore[arg-type]
            filename=d.filename,
            mime_type=d.mime_type,
            size_bytes=d.size_bytes,
            uploaded_by=d.uploaded_by,
            uploaded_at=d.uploaded_at,
            status=d.status,  # type: ignore[arg-type]
            archived=d.archived,
            archived_at=d.archived_at,
        )


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    limit: int
    offset: int


class SignedUrlResponse(BaseModel):
    """Short-lived pre-signed download URL."""

    document_id: str
    url: str
    expires_in_seconds: int
