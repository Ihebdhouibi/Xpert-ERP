"""Vehicle router — CRUD, search, ownership transfer, re-registration, history."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.vehicles import service
from app.modules.vehicles.models import VehicleStatus
from app.modules.vehicles.schemas import (
    OwnershipTransferRequest,
    ReRegistrationRequest,
    VehicleCreateRequest,
    VehicleHistoryOut,
    VehicleListResponse,
    VehicleOut,
    VehicleUpdateRequest,
)
from app.modules.vehicles.service import (
    ConflictError,
    DuplicateVehicleError,
    VehicleNotFoundError,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
logger = get_logger("vehicles.router")


# ---------------------------------------------------------------------------
# List / Search
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=VehicleListResponse,
    dependencies=[require_permission("vehicle.read")],
    summary="List vehicles with optional search by registration or VIN",
)
async def list_vehicles(
    user: AuthUser,
    q: Optional[str] = Query(None, description="Search by registration or VIN"),
    customer_id: Optional[int] = Query(None),
    status: Optional[VehicleStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> VehicleListResponse:
    return await service.list_vehicles(
        db,
        garage_id=user.garage_id,
        search=q,
        customer_id=customer_id,
        status=status,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=VehicleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("vehicle.create")],
    summary="Register a new vehicle",
)
async def create_vehicle(
    body: VehicleCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> VehicleOut:
    try:
        return await service.create_vehicle(db, garage_id=user.garage_id, data=body)
    except DuplicateVehicleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Get one
# ---------------------------------------------------------------------------

@router.get(
    "/{vehicle_id}",
    response_model=VehicleOut,
    dependencies=[require_permission("vehicle.read")],
    summary="Get a vehicle by ID",
)
async def get_vehicle(
    vehicle_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> VehicleOut:
    try:
        return await service.get_vehicle(db, vehicle_id=vehicle_id, garage_id=user.garage_id)
    except VehicleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Update (optimistic concurrency via If-Match header)
# ---------------------------------------------------------------------------

@router.patch(
    "/{vehicle_id}",
    response_model=VehicleOut,
    dependencies=[require_permission("vehicle.update")],
    summary="Update vehicle fields. Send If-Match: <version> to prevent lost updates.",
)
async def update_vehicle(
    vehicle_id: int,
    body: VehicleUpdateRequest,
    user: AuthUser,
    if_match: Annotated[Optional[str], Header(alias="If-Match")] = None,
    db: AsyncSession = Depends(get_db),
) -> VehicleOut:
    expected_version: Optional[int] = None
    if if_match is not None:
        try:
            expected_version = int(if_match.strip('"'))
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="If-Match must be an integer version"
            )
    try:
        return await service.update_vehicle(
            db,
            vehicle_id=vehicle_id,
            garage_id=user.garage_id,
            data=body,
            expected_version=expected_version,
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------

@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[require_permission("vehicle.delete")],
    summary="Soft-delete a vehicle",
)
async def delete_vehicle(
    vehicle_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await service.delete_vehicle(
            db,
            vehicle_id=vehicle_id,
            garage_id=user.garage_id,
            deleted_by=user.user_id or None,
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Ownership transfer
# ---------------------------------------------------------------------------

@router.post(
    "/{vehicle_id}/transfer-ownership",
    response_model=VehicleOut,
    dependencies=[require_permission("vehicle.update")],
    summary="Transfer vehicle ownership to a new customer",
)
async def transfer_ownership(
    vehicle_id: int,
    body: OwnershipTransferRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> VehicleOut:
    try:
        return await service.transfer_ownership(
            db,
            vehicle_id=vehicle_id,
            garage_id=user.garage_id,
            data=body,
            transferred_by=user.user_id or None,
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Re-registration
# ---------------------------------------------------------------------------

@router.post(
    "/{vehicle_id}/re-register",
    response_model=VehicleOut,
    dependencies=[require_permission("vehicle.update")],
    summary="Assign a new registration plate (old plate saved as alias)",
)
async def re_register(
    vehicle_id: int,
    body: ReRegistrationRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> VehicleOut:
    try:
        return await service.re_register(
            db,
            vehicle_id=vehicle_id,
            garage_id=user.garage_id,
            data=body,
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateVehicleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# History view
# ---------------------------------------------------------------------------

@router.get(
    "/{vehicle_id}/history",
    response_model=VehicleHistoryOut,
    dependencies=[require_permission("vehicle.read")],
    summary="Full vehicle history: ownership changes, registration aliases, repair orders",
)
async def get_vehicle_history(
    vehicle_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> VehicleHistoryOut:
    try:
        return await service.get_vehicle_history(
            db, vehicle_id=vehicle_id, garage_id=user.garage_id
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
