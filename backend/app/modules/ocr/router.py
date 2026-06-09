"""OCR pipeline router — /ocr endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.ocr import service
from app.modules.ocr.schemas import (
    ConfirmFieldsRequest,
    IngestionResult,
    OcrExtractionOut,
    OcrRegionRequest,
)
from app.modules.ocr.service import (
    OcrInvalidStateError,
    OcrNotFoundError,
)
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.core.logging import get_logger
from app.modules.documents import repository as doc_repo

router = APIRouter(prefix="/ocr", tags=["ocr"])
logger = get_logger("ocr.router")


@router.post(
    "/enqueue/{document_public_id}",
    response_model=OcrExtractionOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission("document.read")],
    summary="Enqueue OCR processing for a document",
)
async def enqueue_ocr(
    document_public_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> OcrExtractionOut:
    """Create a pending extraction row and immediately kick off processing in the background."""
    document = await doc_repo.get_by_public_id(db, public_id=document_public_id, garage_id=user.garage_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    extraction = await service.enqueue_ocr(db, document_id=document.id)
    background_tasks.add_task(service.process_ocr_job, db, extraction_id=extraction.id)
    return OcrExtractionOut.from_model(extraction, document)


@router.get(
    "/by-document/{document_public_id}",
    response_model=OcrExtractionOut,
    dependencies=[require_permission("document.read")],
    summary="Get the latest cached extraction for a document",
)
async def get_latest_for_document(
    document_public_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> OcrExtractionOut:
    """Return the most recent extraction for a document without re-running OCR."""
    from app.modules.ocr import repository as repo

    document = await doc_repo.get_by_public_id(
        db, public_id=document_public_id, garage_id=user.garage_id
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    extraction = await repo.get_latest_by_document(db, document_id=document.id)
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No extraction for this document"
        )
    return OcrExtractionOut.from_model(extraction, document)


@router.get(
    "/{extraction_id}",
    response_model=OcrExtractionOut,
    dependencies=[require_permission("document.read")],
    summary="Poll OCR extraction status and results",
)
async def get_extraction(
    extraction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OcrExtractionOut:
    """Poll for status updates.  Returns structured fields once processing completes."""
    from app.modules.ocr import repository as repo
    extraction = await repo.get_by_public_id(db, public_id=extraction_id)
    if extraction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR extraction not found")
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    return OcrExtractionOut.from_model(extraction, document)


@router.post(
    "/{extraction_id}/confirm",
    response_model=OcrExtractionOut,
    dependencies=[require_permission("document.read")],
    summary="Human confirms / corrects extracted fields",
)
async def confirm_extraction(
    extraction_id: uuid.UUID,
    body: ConfirmFieldsRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> OcrExtractionOut:
    """
    Operator submits confirmed field values.  Only this endpoint may trigger
    downstream writes — and only for fields the operator explicitly validated.
    """
    try:
        extraction = await service.confirm_fields(
            db,
            extraction_public_id=extraction_id,
            confirmed_fields=body.confirmed_fields,
            reviewer_id=user.user_id,
        )
    except OcrNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR extraction not found")
    except OcrInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    return OcrExtractionOut.from_model(extraction, document)


@router.post(
    "/{extraction_id}/ingest",
    response_model=IngestionResult,
    dependencies=[require_permission("document.read")],
    summary="Confirm reviewed fields and route them to their destination",
)
async def ingest_extraction(
    extraction_id: uuid.UUID,
    body: ConfirmFieldsRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> IngestionResult:
    """
    Persist the operator-reviewed fields (write-back for vehicle / customer) and
    return where the data goes plus, for invoices, a prefill for the create
    dialog.
    """
    try:
        result = await service.ingest_extraction(
            db,
            extraction_public_id=extraction_id,
            confirmed_fields=body.confirmed_fields,
            reviewer_id=user.user_id,
        )
    except OcrNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR extraction not found")
    except OcrInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return result


@router.post(
    "/{extraction_id}/ocr-region",
    dependencies=[require_permission("document.read")],
    summary="OCR a cropped region of the document and return its text",
)
async def ocr_region(
    extraction_id: uuid.UUID,
    body: OcrRegionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run OCR on a user-drawn rectangle of the source document."""
    try:
        text = await service.ocr_region(
            db,
            extraction_public_id=extraction_id,
            box=(body.x1, body.y1, body.x2, body.y2),
        )
    except OcrNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR extraction not found")
    return {"text": text}


@router.post(
    "/{extraction_id}/reject",
    response_model=OcrExtractionOut,
    dependencies=[require_permission("document.read")],
    summary="Human rejects the OCR extraction result",
)
async def reject_extraction(
    extraction_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> OcrExtractionOut:
    """Marks the extraction as failed (operator discards the result)."""
    try:
        extraction = await service.reject_extraction(
            db,
            extraction_public_id=extraction_id,
            reviewer_id=user.user_id,
        )
    except OcrNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR extraction not found")
    return OcrExtractionOut.from_model(extraction)
