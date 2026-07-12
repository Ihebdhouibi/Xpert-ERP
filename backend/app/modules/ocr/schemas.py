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
    document_public_id: Optional[str] = None
    document_category: Optional[str] = None
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
    def from_model(cls, row: Any, document: Any = None) -> "OcrExtractionOut":
        category = getattr(document, "category", None)
        return cls(
            id=str(row.public_id),
            document_id=row.document_id,
            document_public_id=(
                str(document.public_id) if document is not None else None
            ),
            document_category=(
                category.value if hasattr(category, "value") else category
            ),
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


class OcrRegionRequest(BaseModel):
    """A rectangle (rendered-page pixel coords) to OCR on demand."""
    x1: int
    y1: int
    x2: int
    y2: int
    # 0-based page index the rectangle was drawn on (multi-page PDFs).
    page: int = 0


class SuggestFieldRequest(BaseModel):
    """Ask the engine to auto-match a single field from the recognised text."""
    field: str


class IngestLine(BaseModel):
    """One best-effort line item parsed from an invoice (for prefill only)."""
    description: Optional[str] = None
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    line_total: Optional[str] = None


class IngestionResult(BaseModel):
    """Result of an ingest action: where the data goes + an optional prefill.

    For ``vehicle`` / ``customer`` targets the write-back already happened
    server-side and ``prefill`` is null. For invoice targets the caller uses
    ``prefill`` to open the relevant create dialog (no auto-create, because a
    supplier invoice must be linked to a purchase order first).
    """
    target: str  # "vehicle" | "customer" | "supplier_invoice" | "invoice" | "none"
    prefill: Optional["InvoicePrefill"] = None
    # Public id of a record created by the ingest action (e.g. supplier invoice).
    created_id: Optional[str] = None


class InvoicePrefill(BaseModel):
    number: Optional[str] = None
    invoice_date: Optional[str] = None  # ISO date
    due_date: Optional[str] = None  # ISO date
    party: Optional[str] = None  # supplier or client name (free text hint)
    total_ht_cents: Optional[int] = None
    total_ttc_cents: Optional[int] = None
    suggested_lines: list[IngestLine] = []


IngestionResult.model_rebuild()
