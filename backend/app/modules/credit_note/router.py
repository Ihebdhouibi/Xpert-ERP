"""Credit note and refund REST endpoints."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.credit_note import service
from app.modules.credit_note.schemas import (
    CreditNoteCreateRequest,
    CreditNoteListResponse,
    CreditNoteOut,
    RefundCreateRequest,
    RefundOut,
)
from app.modules.credit_note.service import (
    CreditNoteNotFoundError,
    CreditNoteStateError,
    RefundExceedsPaymentError,
    RefundNotFoundError,
)
from app.modules.invoice.service import InvoiceNotFoundError
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/credit-notes", tags=["Credit Notes"])

# ---------------------------------------------------------------------------
# Credit note endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CreditNoteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("credit_note.create")],
    summary="Create a draft credit note",
)
async def create_credit_note(
    request: CreditNoteCreateRequest,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CreditNoteOut:
    try:
        return await service.create_credit_note(
            db, request=request, garage_id=current_user.garage_id, user_id=current_user.user_id
        )
    except InvoiceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CreditNoteStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{cn_id}/issue",
    response_model=CreditNoteOut,
    status_code=status.HTTP_200_OK,
    dependencies=[require_permission("credit_note.issue")],
    summary="Issue a draft credit note (assigns CN number)",
)
async def issue_credit_note(
    cn_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CreditNoteOut:
    try:
        return await service.issue_credit_note(
            db, cn_id, current_user.garage_id, user_id=current_user.user_id
        )
    except CreditNoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CreditNoteStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{cn_id}/void",
    response_model=CreditNoteOut,
    status_code=status.HTTP_200_OK,
    dependencies=[require_permission("credit_note.void")],
    summary="Void an issued credit note",
)
async def void_credit_note(
    cn_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CreditNoteOut:
    try:
        return await service.void_credit_note(
            db, cn_id, current_user.garage_id, user_id=current_user.user_id
        )
    except CreditNoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CreditNoteStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "",
    response_model=CreditNoteListResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[require_permission("credit_note.read")],
    summary="List credit notes",
)
async def list_credit_notes(
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> CreditNoteListResponse:
    return await service.list_credit_notes(
        db, current_user.garage_id, page=page, page_size=page_size
    )


@router.get(
    "/{cn_id}",
    response_model=CreditNoteOut,
    status_code=status.HTTP_200_OK,
    dependencies=[require_permission("credit_note.read")],
    summary="Get credit note by ID",
)
async def get_credit_note(
    cn_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CreditNoteOut:
    try:
        return await service.get_credit_note(db, cn_id, current_user.garage_id)
    except CreditNoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Refund endpoints
# ---------------------------------------------------------------------------

refund_router = APIRouter(prefix="/refunds", tags=["Refunds"])


@refund_router.post(
    "",
    response_model=RefundOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("refund.create")],
    summary="Record a refund against a payment",
)
async def record_refund(
    request: RefundCreateRequest,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RefundOut:
    try:
        return await service.record_refund(
            db, request=request, garage_id=current_user.garage_id, user_id=current_user.user_id
        )
    except RefundNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (RefundExceedsPaymentError, CreditNoteStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except CreditNoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@refund_router.get(
    "/{refund_id}",
    response_model=RefundOut,
    status_code=status.HTTP_200_OK,
    dependencies=[require_permission("refund.read")],
    summary="Get refund by ID",
)
async def get_refund(
    refund_id: int,
    current_user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RefundOut:
    try:
        return await service.get_refund(db, refund_id, current_user.garage_id)
    except RefundNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
