"""Quotation router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.quotation import service
from app.modules.quotation.models import QuotationStatus
from app.modules.quotation.schemas import (
    QuotationCreateRequest,
    QuotationLineCreateRequest,
    QuotationLineUpdateRequest,
    QuotationListResponse,
    QuotationOut,
    QuotationUpdateRequest,
)
from app.modules.quotation.service import (
    QuotationNotFoundError,
    QuotationLineNotFoundError,
    QuotationStateError,
    QuotationVersionError,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/quotations", tags=["quotations"])
logger = get_logger("quotation.router")

_NOT_FOUND = "Quotation not found."
_LINE_NOT_FOUND = "Quotation line not found."
_STATE_ERROR = "Operation not allowed in current status."
_VERSION_ERROR = "Optimistic concurrency conflict; refresh and retry."


def _parse_if_match(if_match: Optional[str]) -> int:
    """Parse the If-Match header into an integer version number."""
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
    response_model=QuotationListResponse,
    dependencies=[require_permission("quotation.read")],
    summary="List quotations",
)
async def list_quotations(
    user: AuthUser,
    customer_id: Optional[int] = Query(None),
    status_filter: Optional[QuotationStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> QuotationListResponse:
    return await service.list_quotations(
        db, user.garage_id, customer_id=customer_id, status=status_filter, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=QuotationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("quotation.create")],
    summary="Create a draft quotation",
)
async def create_quotation(
    user: AuthUser,
    request: QuotationCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    return await service.create_quotation(
        db, request=request, garage_id=user.garage_id, user_id=user.user_id
    )


# ---------------------------------------------------------------------------
# Single quotation
# ---------------------------------------------------------------------------

@router.get(
    "/{quotation_id}",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.read")],
    summary="Get quotation detail",
)
async def get_quotation(
    user: AuthUser,
    quotation_id: int,
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    try:
        return await service.get_quotation(db, quotation_id, user.garage_id)
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


@router.patch(
    "/{quotation_id}",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.update")],
    summary="Update draft quotation header",
)
async def update_quotation(
    user: AuthUser,
    quotation_id: int,
    request: QuotationUpdateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.update_quotation(
            db, quotation_id, user.garage_id, request=request, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except QuotationStateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except QuotationVersionError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_VERSION_ERROR)


@router.delete(
    "/{quotation_id}",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_permission("quotation.update")],
    summary="Soft-delete a draft quotation",
)
async def delete_quotation(
    user: AuthUser,
    quotation_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await service.delete_quotation(db, quotation_id, user.garage_id, user_id=user.user_id)
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except QuotationStateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------

@router.post(
    "/{quotation_id}/lines",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.update")],
    summary="Add a line to a draft quotation",
)
async def add_line(
    user: AuthUser,
    quotation_id: int,
    request: QuotationLineCreateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.add_line(
            db, quotation_id, user.garage_id, request=request, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (QuotationStateError, QuotationVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/{quotation_id}/lines/{line_id}",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.update")],
    summary="Update a line on a draft quotation",
)
async def update_line(
    user: AuthUser,
    quotation_id: int,
    line_id: int,
    request: QuotationLineUpdateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.update_line(
            db, quotation_id, line_id, user.garage_id,
            request=request, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except QuotationLineNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)
    except (QuotationStateError, QuotationVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete(
    "/{quotation_id}/lines/{line_id}",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.update")],
    summary="Remove a line from a draft quotation",
)
async def remove_line(
    user: AuthUser,
    quotation_id: int,
    line_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.remove_line(
            db, quotation_id, line_id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except QuotationLineNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)
    except (QuotationStateError, QuotationVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

@router.post(
    "/{quotation_id}/send",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.send")],
    summary="Send quotation to customer (DRAFT → SENT, assigns doc_number)",
)
async def send_quotation(
    user: AuthUser,
    quotation_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.send_quotation(
            db, quotation_id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (QuotationStateError, QuotationVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{quotation_id}/approve",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.approve_on_behalf")],
    summary="Internally approve a sent quotation (SENT → APPROVED)",
)
async def approve_quotation(
    user: AuthUser,
    quotation_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.approve_quotation(
            db, quotation_id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (QuotationStateError, QuotationVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{quotation_id}/reject",
    response_model=QuotationOut,
    dependencies=[require_permission("quotation.update")],
    summary="Reject a sent quotation (SENT → REJECTED)",
)
async def reject_quotation(
    user: AuthUser,
    quotation_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> QuotationOut:
    version = _parse_if_match(if_match)
    try:
        return await service.reject_quotation(
            db, quotation_id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except QuotationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (QuotationStateError, QuotationVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
