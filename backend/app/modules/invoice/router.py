"""Invoice router."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.invoice import service
from app.modules.invoice.models import InvoiceStatus
from app.modules.invoice.schemas import (
    InvoiceCreateRequest,
    InvoiceLineCreateRequest,
    InvoiceLineUpdateRequest,
    InvoiceListResponse,
    InvoiceOut,
    InvoiceUpdateRequest,
)
from app.modules.invoice.service import (
    InvoiceNotFoundError,
    InvoiceLineNotFoundError,
    InvoiceStateError,
    InvoiceVersionError,
    QuotationAlreadyConvertedError,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

_NOT_FOUND = "Invoice not found."
_LINE_NOT_FOUND = "Invoice line not found."
_STATE_ERR = "Operation not allowed in current status."
_VERSION_ERR = "Optimistic concurrency conflict; refresh and retry."


def _parse_if_match(if_match: Optional[str]) -> int:
    if not if_match:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="If-Match header required.")
    try:
        return int(if_match.strip('"').strip())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="If-Match must be an integer version.")


# ---------------------------------------------------------------------------
# List + create
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=InvoiceListResponse,
    dependencies=[require_permission("invoice.read")],
    summary="List invoices",
)
async def list_invoices(
    user: AuthUser,
    customer_id: Optional[int] = Query(None),
    status_filter: Optional[InvoiceStatus] = Query(None, alias="status"),
    quotation_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    return await service.list_invoices(
        db, user.garage_id,
        customer_id=customer_id, status=status_filter,
        quotation_id=quotation_id, page=page, page_size=page_size,
    )


@router.post(
    "",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("invoice.create")],
    summary="Create a draft invoice",
)
async def create_invoice(
    user: AuthUser,
    request: InvoiceCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    return await service.create_invoice(
        db, request=request, garage_id=user.garage_id, user_id=user.user_id
    )


# ---------------------------------------------------------------------------
# Convert quotation → invoice  (lives under /invoices for clarity)
# ---------------------------------------------------------------------------

@router.post(
    "/from-quotation/{quotation_id}",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("quotation.convert")],
    summary="Convert an approved/sent quotation into a draft invoice",
)
async def convert_quotation(
    user: AuthUser,
    quotation_id: int,
    due_at: Optional[datetime] = Body(None),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        return await service.convert_quotation(
            db, quotation_id, user.garage_id, due_at=due_at, user_id=user.user_id
        )
    except Exception as exc:
        # Import lazily to avoid circular import at module load
        from app.modules.quotation.service import QuotationNotFoundError
        if isinstance(exc, QuotationNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found.")
        if isinstance(exc, QuotationAlreadyConvertedError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if isinstance(exc, InvoiceStateError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        raise


# ---------------------------------------------------------------------------
# Single invoice
# ---------------------------------------------------------------------------

@router.get(
    "/{invoice_id}",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.read")],
    summary="Get invoice detail",
)
async def get_invoice(
    user: AuthUser,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        return await service.get_invoice(db, invoice_id, user.garage_id)
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.update")],
    summary="Update draft invoice header",
)
async def update_invoice(
    user: AuthUser,
    invoice_id: int,
    request: InvoiceUpdateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        return await service.update_invoice(
            db, invoice_id, user.garage_id,
            request=request, expected_version=version, user_id=user.user_id,
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except InvoiceStateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvoiceVersionError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_VERSION_ERR)


@router.delete(
    "/{invoice_id}",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_permission("invoice.update")],
    summary="Soft-delete a draft invoice",
)
async def delete_invoice(
    user: AuthUser,
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await service.delete_invoice(db, invoice_id, user.garage_id, user_id=user.user_id)
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except InvoiceStateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------

@router.post(
    "/{invoice_id}/lines",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.update")],
    summary="Add a line to a draft invoice",
)
async def add_line(
    user: AuthUser,
    invoice_id: int,
    request: InvoiceLineCreateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        return await service.add_line(
            db, invoice_id, user.garage_id,
            request=request, expected_version=version, user_id=user.user_id,
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/{invoice_id}/lines/{line_id}",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.update")],
    summary="Update a line on a draft invoice",
)
async def update_line(
    user: AuthUser,
    invoice_id: int,
    line_id: int,
    request: InvoiceLineUpdateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        return await service.update_line(
            db, invoice_id, line_id, user.garage_id,
            request=request, expected_version=version, user_id=user.user_id,
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except InvoiceLineNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete(
    "/{invoice_id}/lines/{line_id}",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.update")],
    summary="Remove a line from a draft invoice",
)
async def remove_line(
    user: AuthUser,
    invoice_id: int,
    line_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        return await service.remove_line(
            db, invoice_id, line_id, user.garage_id,
            expected_version=version, user_id=user.user_id,
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except InvoiceLineNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

@router.post(
    "/{invoice_id}/issue",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.issue")],
    summary="Issue invoice (DRAFT → ISSUED), assigns doc_number",
)
async def issue_invoice(
    user: AuthUser,
    invoice_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        return await service.issue_invoice(
            db, invoice_id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.cancel")],
    summary="Cancel invoice (DRAFT/ISSUED → CANCELLED)",
)
async def cancel_invoice(
    user: AuthUser,
    invoice_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        return await service.cancel_invoice(
            db, invoice_id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
