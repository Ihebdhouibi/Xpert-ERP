"""OCR pipeline router — /ocr endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.ocr import service
from app.modules.ocr.schemas import ConfirmFieldsRequest, OcrExtractionOut
from app.modules.ocr.service import (
    OcrInvalidStateError,
    OcrNotFoundError,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post(
    "/enqueue/{document_id}",
    response_model=OcrExtractionOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission("document.read")],
    summary="Enqueue OCR processing for a document",
)
async def enqueue_ocr(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> OcrExtractionOut:
    """Create a pending extraction row and immediately kick off processing in the background."""
    extraction = await service.enqueue_ocr(db, document_id=document_id)
    background_tasks.add_task(service.process_ocr_job, db, extraction_id=extraction.id)
    return OcrExtractionOut.from_model(extraction)


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
    return OcrExtractionOut.from_model(extraction)


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
    return OcrExtractionOut.from_model(extraction)


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
