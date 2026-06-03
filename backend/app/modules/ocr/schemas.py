"""Pydantic schemas for the OCR extraction module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.modules.ocr.models import OcrStatus


class OcrExtractionOut(BaseModel):
    id: str  # public_id as string
    document_id: int
    engine_version: str
    status: OcrStatus
    raw_text: Optional[str]
    structured_fields: Optional[dict[str, Any]]
    confidence_scores: Optional[dict[str, float]]
    created_at: datetime
    processed_at: Optional[datetime]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]

    @classmethod
    def from_model(cls, row: Any) -> "OcrExtractionOut":
        return cls(
            id=str(row.public_id),
            document_id=row.document_id,
            engine_version=row.engine_version,
            status=row.status,
            raw_text=row.raw_text,
            structured_fields=row.structured_fields,
            confidence_scores=row.confidence_scores,
            created_at=row.created_at,
            processed_at=row.processed_at,
            reviewed_by=row.reviewed_by,
            reviewed_at=row.reviewed_at,
        )


class ConfirmFieldsRequest(BaseModel):
    """Fields that the human operator has reviewed and confirmed / corrected."""
    confirmed_fields: dict[str, str]
