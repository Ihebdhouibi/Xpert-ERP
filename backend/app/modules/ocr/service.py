"""OCR pipeline business logic.

Critical safety rule:
    Fields whose OCR confidence is BELOW the configured threshold for that field
    are flagged as `needs_review` and are NEVER auto-written to any other table.
    Only `confirm_fields()` — triggered by an explicit human action — may write
    confirmed values to vehicle / customer models.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.customer import repository as customer_repo
from app.modules.documents import repository as doc_repo
from app.modules.documents import storage as doc_storage
from app.modules.documents.models import DocumentCategory, OwnerEntityType
from app.modules.ocr import repository as ocr_repo
from app.modules.ocr.engine import PaddleOcrEngine
from app.modules.ocr.extractors import (
    FieldMap,
    extract_carte_grise,
    extract_national_id,
)
from app.modules.ocr.models import OcrExtraction, OcrStatus
from app.modules.vehicles import repository as vehicle_repo

logger = get_logger("ocr.service")

# Categories that trigger OCR automatically on upload
OCR_TRIGGER_CATEGORIES = {
    DocumentCategory.registration_card,
    DocumentCategory.id_doc,
}


# ---------------------------------------------------------------------------
# Per-field confidence thresholds
# ---------------------------------------------------------------------------

def _threshold(field_name: str) -> float:
    cfg = get_settings()
    thresholds = {
        "immatriculation": cfg.cfg_ocr_confidence_threshold_immatriculation,
        "vin": cfg.cfg_ocr_confidence_threshold_vin,
        "date_mise_en_circulation": cfg.cfg_ocr_confidence_threshold_date,
        "date_naissance": cfg.cfg_ocr_confidence_threshold_date,
        "nom": cfg.cfg_ocr_confidence_threshold_nom,
        "prenom": cfg.cfg_ocr_confidence_threshold_nom,
        "numero_cin": cfg.cfg_ocr_confidence_threshold_cin,
    }
    return thresholds.get(field_name, cfg.cfg_ocr_confidence_threshold_default)


def _evaluate_fields(fields: FieldMap) -> tuple[dict[str, Any], dict[str, float], bool]:
    """
    Returns:
        structured_fields: {field: value}
        confidence_scores: {field: confidence}
        needs_review: True if any field is below its threshold
    """
    structured: dict[str, Any] = {}
    scores: dict[str, float] = {}
    needs_review = False

    for field, (value, confidence) in fields.items():
        structured[field] = value
        scores[field] = confidence
        if confidence < _threshold(field):
            needs_review = True

    return structured, scores, needs_review


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def enqueue_ocr(db: AsyncSession, *, document_id: int) -> OcrExtraction:
    """Create a pending OCR extraction row for a document."""
    extraction = await ocr_repo.create(db, document_id=document_id)
    logger.info("ocr_enqueued", extraction_id=extraction.id, document_id=document_id)
    return extraction


async def process_ocr_job(db: AsyncSession, *, extraction_id: int) -> OcrExtraction:
    """
    Download the document from S3, run PaddleOCR, extract structured fields,
    evaluate confidence thresholds, and persist results.

    Status transitions:
        pending → processing → completed | needs_review | failed
    """
    extraction = await ocr_repo.get_by_id(db, extraction_id=extraction_id)
    if extraction is None:
        raise OcrNotFoundError(f"OcrExtraction {extraction_id} not found")

    # Mark as processing
    await ocr_repo.update_status(db, extraction_id=extraction_id, status=OcrStatus.processing)

    try:
        document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
        if document is None:
            raise OcrDocumentMissingError(f"Document {extraction.document_id} not found")

        cfg = get_settings()
        image_bytes = await doc_storage.download_object(
            bucket=cfg.s3_bucket_documents, key=document.storage_key
        )

        engine = PaddleOcrEngine.get()
        raw_result = await engine.run_ocr(image_bytes)

        # Choose extractor based on document category
        if document.category == DocumentCategory.registration_card:
            fields = extract_carte_grise(raw_result)
        elif document.category == DocumentCategory.id_doc:
            fields = extract_national_id(raw_result)
        else:
            fields = {}

        structured, scores, needs_review = _evaluate_fields(fields)
        final_status = OcrStatus.needs_review if needs_review else OcrStatus.completed

        await ocr_repo.update_status(
            db,
            extraction_id=extraction_id,
            status=final_status,
            raw_text=raw_result.full_text,
            structured_fields=structured,
            confidence_scores=scores,
            processed_at=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "ocr_processed",
            extraction_id=extraction_id,
            status=final_status,
            field_count=len(structured),
        )

    except Exception as exc:
        logger.error("ocr_failed", extraction_id=extraction_id, error=str(exc))
        await ocr_repo.update_status(
            db,
            extraction_id=extraction_id,
            status=OcrStatus.failed,
            processed_at=datetime.now(tz=timezone.utc),
        )
        raise

    refreshed = await ocr_repo.get_by_id(db, extraction_id=extraction_id)
    assert refreshed is not None
    return refreshed


async def confirm_fields(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    confirmed_fields: dict[str, str],
    reviewer_id: int,
) -> OcrExtraction:
    """
    Human confirms (or corrects) extracted field values.

    This is the ONLY place where OCR results are written to vehicle / customer
    tables. Confirmed fields are merged into the extraction row, all confirmed
    fields receive confidence = 1.0 (human-verified), and the owning entity
    (vehicle or customer) is patched based on the document category.
    """
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))

    if extraction.status not in (OcrStatus.completed, OcrStatus.needs_review):
        raise OcrInvalidStateError(
            f"Cannot confirm fields for extraction in status {extraction.status}"
        )

    # Merge confirmed values into structured_fields
    merged = dict(extraction.structured_fields or {})
    merged.update(confirmed_fields)

    # All confirmed fields get confidence = 1.0 (human-verified)
    merged_scores = dict(extraction.confidence_scores or {})
    for field in confirmed_fields:
        merged_scores[field] = 1.0

    await ocr_repo.update_status(
        db,
        extraction_id=extraction.id,
        status=OcrStatus.completed,
        structured_fields=merged,
        confidence_scores=merged_scores,
    )
    await ocr_repo.mark_reviewed(
        db,
        extraction_id=extraction.id,
        reviewed_by=reviewer_id,
        reviewed_at=datetime.now(tz=timezone.utc),
    )

    # Write confirmed fields back to the owning entity
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    if document is not None and document.owner_entity_id is not None:
        if (
            document.category == DocumentCategory.registration_card
            and document.owner_entity_type == OwnerEntityType.vehicle.value
        ):
            wrote = await vehicle_repo.patch_from_ocr(
                db,
                vehicle_id=document.owner_entity_id,
                garage_id=document.garage_id,
                fields=merged,
            )
            logger.info(
                "ocr_vehicle_writeback",
                vehicle_id=document.owner_entity_id,
                wrote=wrote,
                fields=list(merged.keys()),
            )
        elif (
            document.category == DocumentCategory.id_doc
            and document.owner_entity_type == OwnerEntityType.customer.value
        ):
            wrote = await customer_repo.patch_from_ocr(
                db,
                customer_id=document.owner_entity_id,
                garage_id=document.garage_id,
                fields=merged,
            )
            logger.info(
                "ocr_customer_writeback",
                customer_id=document.owner_entity_id,
                wrote=wrote,
                fields=list(merged.keys()),
            )

    refreshed = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    assert refreshed is not None
    return refreshed


async def reject_extraction(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    reviewer_id: int,
) -> OcrExtraction:
    """Mark an extraction as failed (human rejected the result)."""
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))

    await ocr_repo.update_status(
        db, extraction_id=extraction.id, status=OcrStatus.failed
    )
    await ocr_repo.mark_reviewed(
        db,
        extraction_id=extraction.id,
        reviewed_by=reviewer_id,
        reviewed_at=datetime.now(tz=timezone.utc),
    )

    refreshed = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    assert refreshed is not None
    return refreshed


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OcrNotFoundError(Exception):
    pass


class OcrDocumentMissingError(Exception):
    pass


class OcrInvalidStateError(Exception):
    pass
