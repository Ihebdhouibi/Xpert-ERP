"""Delivery Note router — CRUD and lifecycle endpoints."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.auth.models import AppUser
from app.modules.delivery_note import service
from app.modules.delivery_note.models import DeliveryNoteStatus
from app.modules.delivery_note.schemas import (
    DeliveryNoteCreateRequest,
    DeliveryNoteLineCreateRequest,
    DeliveryNoteLineUpdateRequest,
    DeliveryNoteListResponse,
    DeliveryNoteOut,
    DeliveryNoteUpdateRequest,
)
from app.modules.customer.credit_service import CreditLimitExceededError
from app.modules.delivery_note.service import (
    DeliveryNoteNotFoundError,
    DeliveryNoteLineNotFoundError,
    DeliveryNoteStateError,
    DeliveryNoteVersionError,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/delivery-notes", tags=["delivery-notes"])
logger = get_logger("delivery_note.router")

_NOT_FOUND = "Delivery note not found."
_LINE_NOT_FOUND = "Delivery note line not found."
_STATE_ERR = "Operation not allowed in current status."
_VERSION_ERR = "Optimistic concurrency conflict; refresh and retry."


async def _resolve_user_id(db: AsyncSession, public_id: str) -> Optional[int]:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(AppUser.id).where(AppUser.public_id == uid))
    row = result.first()
    return row[0] if row else None


def _parse_if_match(if_match: Optional[str]) -> int:
    if not if_match:
        raise HTTPException(status.HTTP_428_PRECONDITION_REQUIRED, detail="If-Match header required.")
    try:
        return int(if_match.strip('"').strip())
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="If-Match must be an integer version.")


# ---------------------------------------------------------------------------
# List + Create
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=DeliveryNoteListResponse,
    dependencies=[require_permission("invoice.read")],
    summary="List delivery notes",
)
async def list_delivery_notes(
    user: AuthUser,
    customer_id: Optional[int] = Query(None),
    status_filter: Optional[DeliveryNoteStatus] = Query(None, alias="status"),
    available_for_invoice: bool = Query(False),
    search: Optional[str] = Query(None, max_length=100),
    sort_by: Optional[str] = Query(None),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteListResponse:
    return await service.list_delivery_notes(
        db, user.garage_id,
        customer_id=customer_id, status=status_filter,
        available_for_invoice=available_for_invoice,
        search=search, sort_by=sort_by, sort_dir=sort_dir,
        page=page, page_size=page_size,
    )


@router.post(
    "",
    response_model=DeliveryNoteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("invoice.create")],
    summary="Create a draft delivery note",
)
async def create_delivery_note(
    user: AuthUser,
    body: DeliveryNoteCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    return await service.create_delivery_note(
        db, request=body, garage_id=user.garage_id, user_id=uid or 0
    )


# ---------------------------------------------------------------------------
# Single item
# ---------------------------------------------------------------------------

@router.get(
    "/{public_id}",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.read")],
    summary="Get delivery note detail",
)
async def get_delivery_note(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    try:
        return await service.get_delivery_note(db, public_id, user.garage_id)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)


@router.patch(
    "/{public_id}",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.update")],
    summary="Update a draft delivery note header",
)
async def update_delivery_note(
    public_id: str,
    user: AuthUser,
    body: DeliveryNoteUpdateRequest,
    if_match: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    version = _parse_if_match(if_match)
    try:
        return await service.update_delivery_note(
            db, public_id, user.garage_id, request=body, expected_version=version, user_id=uid or 0
        )
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except DeliveryNoteVersionError:
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, _VERSION_ERR)


@router.delete(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[require_permission("invoice.update")],
    summary="Delete a draft or cancelled delivery note",
)
async def delete_delivery_note(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        await service.delete_delivery_note(db, public_id, user.garage_id, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Line management
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/lines",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.update")],
    summary="Add a line to a draft delivery note",
)
async def add_line(
    public_id: str,
    user: AuthUser,
    body: DeliveryNoteLineCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.add_line(db, public_id, user.garage_id, request=body, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.patch(
    "/{public_id}/lines/{line_id}",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.update")],
    summary="Update a line in a draft delivery note",
)
async def update_line(
    public_id: str,
    line_id: int,
    user: AuthUser,
    body: DeliveryNoteLineUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.update_line(
            db, public_id, line_id, user.garage_id, request=body, user_id=uid or 0
        )
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteLineNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _LINE_NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.delete(
    "/{public_id}/lines/{line_id}",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.update")],
    summary="Remove a line from a draft delivery note",
)
async def remove_line(
    public_id: str,
    line_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.remove_line(db, public_id, line_id, user.garage_id, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteLineNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _LINE_NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/issue",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.issue")],
    summary="Issue a delivery note (assign doc number, lock lines)",
)
async def issue_delivery_note(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.issue_delivery_note(db, public_id, user.garage_id, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except CreditLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "credit_limit_exceeded",
                "customer_public_id": e.customer_public_id,
                "doc_type": "delivery_note",
                "outstanding": e.outstanding,
                "limit": e.limit,
                "additional": e.additional,
                "message": (
                    f"Limite de crédit dépassée. "
                    f"Encours : {e.outstanding / 100:.2f} €, "
                    f"BL : {e.additional / 100:.2f} €, "
                    f"Limite : {e.limit / 100:.2f} €."
                ),
            },
        )


@router.post(
    "/{public_id}/mark-delivered",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.issue")],
    summary="Mark a delivery note as delivered",
)
async def mark_delivered(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.mark_delivered(db, public_id, user.garage_id, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post(
    "/{public_id}/cancel",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.cancel")],
    summary="Cancel a draft or issued delivery note",
)
async def cancel_delivery_note(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.cancel_delivery_note(db, public_id, user.garage_id, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post(
    "/{public_id}/convert-to-invoice",
    response_model=DeliveryNoteOut,
    dependencies=[require_permission("invoice.create")],
    summary="Convert an issued/delivered BL to a draft Invoice",
)
async def convert_to_invoice(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.convert_to_invoice(db, public_id, user.garage_id, user_id=uid or 0)
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


# ---------------------------------------------------------------------------
# Create from quotation
# ---------------------------------------------------------------------------

@router.post(
    "/from-quotation/{quotation_id}",
    response_model=DeliveryNoteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("invoice.create")],
    summary="Create a draft delivery note from a quotation",
)
async def create_from_quotation(
    quotation_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.from_quotation(
            db, quotation_id, user.garage_id, user_id=uid or 0
        )
    except service.DeliveryNoteNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


# ---------------------------------------------------------------------------
# Create from repair order
# ---------------------------------------------------------------------------

@router.post(
    "/from-repair-order/{ro_public_id}",
    response_model=DeliveryNoteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("invoice.create")],
    summary="Create a draft delivery note pre-linked to a repair order",
)
async def create_from_repair_order(
    ro_public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DeliveryNoteOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.from_repair_order(
            db, ro_public_id, user.garage_id, user_id=uid or 0
        )
    except DeliveryNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repair order not found.")
    except DeliveryNoteStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
