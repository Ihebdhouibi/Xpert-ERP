"""Bon de Retour router — CRUD, lifecycle, and avoir creation endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.auth.models import AppUser
from app.modules.bon_de_retour import service
from app.modules.bon_de_retour.models import BonDeRetourPartyType, BonDeRetourStatus, SupplierCreditNoteStatus
from app.modules.bon_de_retour.schemas import (
    BonDeRetourCreateRequest,
    BonDeRetourLineCreateRequest,
    BonDeRetourLineUpdateRequest,
    BonDeRetourListResponse,
    BonDeRetourOut,
    BonDeRetourUpdateRequest,
    CreateCreditNoteRequest,
    CreateSupplierCreditNoteRequest,
    SupplierCreditNoteListResponse,
    SupplierCreditNoteOut,
)
from app.modules.bon_de_retour.service import (
    BonDeRetourLineNotFoundError,
    BonDeRetourNotFoundError,
    BonDeRetourStateError,
    BonDeRetourVersionError,
    SupplierCreditNoteNotFoundError,
)
from app.modules.parts.stock_service import NegativeStockError
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/bon-de-retour", tags=["bon-de-retour"])
logger = get_logger("bon_de_retour.router")

_NOT_FOUND = "Bon de retour not found."
_LINE_NOT_FOUND = "Bon de retour line not found."
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
    response_model=BonDeRetourListResponse,
    dependencies=[require_permission("bon_de_retour.read")],
    summary="List bon de retour",
)
async def list_bon_de_retour(
    user: AuthUser,
    party_type: Optional[BonDeRetourPartyType] = Query(None),
    status_filter: Optional[BonDeRetourStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourListResponse:
    return await service.list_bon_de_retour(
        db, user.garage_id, party_type=party_type, status=status_filter, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=BonDeRetourOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("bon_de_retour.create")],
    summary="Create a draft bon de retour",
)
async def create_bon_de_retour(
    user: AuthUser,
    body: BonDeRetourCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.create_bon_de_retour(db, request=body, garage_id=user.garage_id, user_id=uid or 0)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


# ---------------------------------------------------------------------------
# Supplier credit note list (must come BEFORE /{public_id} to avoid shadowing)
# ---------------------------------------------------------------------------

@router.get(
    "/supplier-credit-notes",
    response_model=SupplierCreditNoteListResponse,
    dependencies=[require_permission("supplier_credit_note.read")],
    summary="List supplier credit notes (avoirs fournisseur)",
)
async def list_supplier_credit_notes(
    user: AuthUser,
    status_filter: Optional[SupplierCreditNoteStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> SupplierCreditNoteListResponse:
    return await service.list_supplier_credit_notes(
        db, user.garage_id, status=status_filter, page=page, page_size=page_size
    )


# ---------------------------------------------------------------------------
# Single item
# ---------------------------------------------------------------------------

@router.get(
    "/{public_id}",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.read")],
    summary="Get bon de retour detail",
)
async def get_bon_de_retour(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    try:
        return await service.get_bon_de_retour(db, public_id, user.garage_id)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)


@router.patch(
    "/{public_id}",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.update")],
    summary="Update a draft bon de retour header",
)
async def update_bon_de_retour(
    public_id: str,
    user: AuthUser,
    body: BonDeRetourUpdateRequest,
    if_match: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    version = _parse_if_match(if_match)
    try:
        return await service.update_bon_de_retour(
            db, public_id, user.garage_id, request=body, expected_version=version, user_id=uid or 0
        )
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except BonDeRetourVersionError:
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, _VERSION_ERR)


@router.delete(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[require_permission("bon_de_retour.update")],
    summary="Delete a draft or cancelled bon de retour",
)
async def delete_bon_de_retour(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        await service.delete_bon_de_retour(db, public_id, user.garage_id, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Line management
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/lines",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.update")],
    summary="Add a line to a draft bon de retour",
)
async def add_line(
    public_id: str,
    user: AuthUser,
    body: BonDeRetourLineCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.add_line(db, public_id, user.garage_id, request=body, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.patch(
    "/{public_id}/lines/{line_id}",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.update")],
    summary="Update a line in a draft bon de retour",
)
async def update_line(
    public_id: str,
    line_id: int,
    user: AuthUser,
    body: BonDeRetourLineUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.update_line(db, public_id, line_id, user.garage_id, request=body, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourLineNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _LINE_NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.delete(
    "/{public_id}/lines/{line_id}",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.update")],
    summary="Remove a line from a draft bon de retour",
)
async def remove_line(
    public_id: str,
    line_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.remove_line(db, public_id, line_id, user.garage_id, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourLineNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _LINE_NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/confirm",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.confirm")],
    summary="Confirm a bon de retour (assign number, apply stock movement)",
)
async def confirm_bon_de_retour(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.confirm_bon_de_retour(db, public_id, user.garage_id, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except NegativeStockError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post(
    "/{public_id}/cancel",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.cancel")],
    summary="Cancel a draft bon de retour",
)
async def cancel_bon_de_retour(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.cancel_bon_de_retour(db, public_id, user.garage_id, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post(
    "/{public_id}/reverse",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("bon_de_retour.reverse")],
    summary="Reverse a confirmed bon de retour (undo stock movements)",
)
async def reverse_bon_de_retour(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.reverse_bon_de_retour(db, public_id, user.garage_id, user_id=uid or 0)
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except NegativeStockError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


# ---------------------------------------------------------------------------
# Avoir creation
# ---------------------------------------------------------------------------

@router.post(
    "/{public_id}/create-credit-note",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("credit_note.create")],
    summary="Create + issue a client avoir from this bon de retour",
)
async def create_credit_note(
    public_id: str,
    user: AuthUser,
    body: CreateCreditNoteRequest,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.create_credit_note_for_br(
            db, public_id, user.garage_id, request=body, user_id=uid or 0
        )
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post(
    "/{public_id}/create-supplier-credit-note",
    response_model=BonDeRetourOut,
    dependencies=[require_permission("supplier_credit_note.create")],
    summary="Create + issue a supplier avoir (avoir fournisseur) from this bon de retour",
)
async def create_supplier_credit_note(
    public_id: str,
    user: AuthUser,
    body: CreateSupplierCreditNoteRequest,
    db: AsyncSession = Depends(get_db),
) -> BonDeRetourOut:
    uid = await _resolve_user_id(db, user.public_id)
    try:
        return await service.create_supplier_credit_note_for_br(
            db, public_id, user.garage_id, request=body, user_id=uid or 0
        )
    except BonDeRetourNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    except BonDeRetourStateError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.get(
    "/supplier-credit-notes/{scn_id}",
    response_model=SupplierCreditNoteOut,
    dependencies=[require_permission("supplier_credit_note.read")],
    summary="Get a supplier avoir by id",
)
async def get_supplier_credit_note(
    scn_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SupplierCreditNoteOut:
    try:
        return await service.get_supplier_credit_note(db, scn_id, user.garage_id)
    except SupplierCreditNoteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier credit note not found.")
