from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.routing import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.supplier.models import SupplierStatus
from app.modules.supplier.repository import SupplierPartPriceRepository, SupplierRepository
from app.modules.supplier.service import (
    PartNotFoundForPriceError,
    SupplierNotFoundError,
    SupplierVersionConflictError,
    add_supplier_price,
    create_supplier,
    delete_supplier,
    get_part_price_comparison,
    update_supplier,
)
from app.core.logging import get_logger

router = APIRouter(tags=["suppliers"])
logger = get_logger("supplier.router")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    payment_terms_days: Optional[int] = Field(None, ge=0)
    average_delivery_days: Optional[int] = Field(None, ge=0)


class SupplierUpdateRequest(BaseModel):
    version: int
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    payment_terms_days: Optional[int] = Field(None, ge=0)
    average_delivery_days: Optional[int] = Field(None, ge=0)
    status: Optional[SupplierStatus] = None


class SupplierSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    payment_terms_days: Optional[int]
    average_delivery_days: Optional[int]
    reliability_score: Optional[float]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _remap_public_id(cls, data: Any) -> Any:
        if hasattr(data, "public_id"):
            data.__dict__["id"] = str(data.public_id)
        return data


class SupplierListResponse(BaseModel):
    items: list[SupplierSummary]
    total: int
    page: int
    page_size: int


class SupplierPriceCreateRequest(BaseModel):
    part_public_id: str = Field(..., description="Catalog part public_id (UUID)")
    unit_price_minor: int = Field(..., gt=0)
    currency: str = Field("MAD", min_length=3, max_length=3)
    effective_from: date


class PriceEntryResponse(BaseModel):
    id: int
    part_public_id: str
    part_name: str
    part_sku: str
    unit_price_minor: int
    currency: str
    effective_from: date
    effective_to: Optional[date]
    created_at: datetime


class PriceComparisonItem(BaseModel):
    supplier_public_id: str
    supplier_name: str
    average_delivery_days: Optional[int]
    reliability_score: Optional[float]
    unit_price_minor: int
    currency: str
    effective_from: str
    effective_to: Optional[str]


# ---------------------------------------------------------------------------
# Supplier CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers",
    response_model=SupplierListResponse,
    dependencies=[require_permission("supplier.read")],
)
async def list_suppliers(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None,
    status: Optional[SupplierStatus] = None,
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SupplierListResponse:
    items, total = await SupplierRepository.list(
        db,
        garage_id=user.garage_id,
        search=search,
        status=status,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    return SupplierListResponse(
        items=[SupplierSummary.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/suppliers",
    status_code=http_status.HTTP_201_CREATED,
    response_model=SupplierSummary,
    dependencies=[require_permission("supplier.create")],
)
async def create_supplier_endpoint(
    body: SupplierCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SupplierSummary:
    supplier = await create_supplier(
        db,
        garage_id=user.garage_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        payment_terms_days=body.payment_terms_days,
        average_delivery_days=body.average_delivery_days,
    )
    await db.commit()
    await db.refresh(supplier)
    return SupplierSummary.model_validate(supplier)


@router.get(
    "/suppliers/{public_id}",
    response_model=SupplierSummary,
    dependencies=[require_permission("supplier.read")],
)
async def get_supplier(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SupplierSummary:
    supplier = await SupplierRepository.get_by_public_id(db, user.garage_id, public_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return SupplierSummary.model_validate(supplier)


@router.put(
    "/suppliers/{public_id}",
    response_model=SupplierSummary,
    dependencies=[require_permission("supplier.update")],
)
async def update_supplier_endpoint(
    public_id: str,
    body: SupplierUpdateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SupplierSummary:
    update_data = body.model_dump(exclude={"version"}, exclude_none=True)
    try:
        supplier = await update_supplier(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            submitted_version=body.version,
            **update_data,
        )
        await db.commit()
        await db.refresh(supplier)
        return SupplierSummary.model_validate(supplier)
    except SupplierNotFoundError:
        raise HTTPException(status_code=404, detail="Supplier not found")
    except SupplierVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "current_version": e.current_version,
                "submitted_version": e.submitted_version,
            },
        )


@router.delete(
    "/suppliers/{public_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("supplier.update")],
)
async def delete_supplier_endpoint(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_supplier(db, garage_id=user.garage_id, public_id=public_id)
        await db.commit()
    except SupplierNotFoundError:
        raise HTTPException(status_code=404, detail="Supplier not found")


# ---------------------------------------------------------------------------
# Supplier price history
# ---------------------------------------------------------------------------


@router.get(
    "/suppliers/{public_id}/prices",
    response_model=list[PriceEntryResponse],
    dependencies=[require_permission("supplier.read")],
)
async def list_supplier_prices(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PriceEntryResponse]:
    supplier = await SupplierRepository.get_by_public_id(db, user.garage_id, public_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    rows = await SupplierPartPriceRepository.list_history(
        db, supplier.id, limit=limit, offset=offset
    )
    return [
        PriceEntryResponse(
            id=price.id,
            part_public_id=part_public_id,
            part_name=part_name,
            part_sku=part_sku,
            unit_price_minor=price.unit_price_minor,
            currency=price.currency,
            effective_from=price.effective_from,
            effective_to=price.effective_to,
            created_at=price.created_at,
        )
        for price, part_public_id, part_name, part_sku in rows
    ]


@router.post(
    "/suppliers/{public_id}/prices",
    status_code=http_status.HTTP_201_CREATED,
    response_model=PriceEntryResponse,
    dependencies=[require_permission("supplier.update")],
)
async def add_supplier_price_endpoint(
    public_id: str,
    body: SupplierPriceCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PriceEntryResponse:
    try:
        price = await add_supplier_price(
            db,
            garage_id=user.garage_id,
            supplier_public_id=public_id,
            part_public_id=body.part_public_id,
            unit_price_minor=body.unit_price_minor,
            currency=body.currency,
            effective_from=body.effective_from,
        )
        await db.commit()
        await db.refresh(price)
    except SupplierNotFoundError:
        raise HTTPException(status_code=404, detail="Supplier not found")
    except PartNotFoundForPriceError:
        raise HTTPException(status_code=404, detail="Part not found")

    # Re-fetch with part info for the response
    rows = await SupplierPartPriceRepository.list_history(
        db, price.supplier_id, limit=1, offset=0
    )
    # Find the newly created entry (highest id)
    rows_for_new = [r for r in rows if r[0].id == price.id]
    if rows_for_new:
        p, part_public_id, part_name, part_sku = rows_for_new[0]
        return PriceEntryResponse(
            id=p.id,
            part_public_id=part_public_id,
            part_name=part_name,
            part_sku=part_sku,
            unit_price_minor=p.unit_price_minor,
            currency=p.currency,
            effective_from=p.effective_from,
            effective_to=p.effective_to,
            created_at=p.created_at,
        )

    # Fallback: return without part name (should not happen)
    return PriceEntryResponse(
        id=price.id,
        part_public_id=body.part_public_id,
        part_name="",
        part_sku="",
        unit_price_minor=price.unit_price_minor,
        currency=price.currency,
        effective_from=price.effective_from,
        effective_to=price.effective_to,
        created_at=price.created_at,
    )


# ---------------------------------------------------------------------------
# Part price comparison (cross-supplier view)
# ---------------------------------------------------------------------------


@router.get(
    "/parts/{part_public_id}/supplier-prices",
    response_model=list[PriceComparisonItem],
    dependencies=[require_permission("supplier.read")],
)
async def get_part_supplier_prices(
    part_public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    at: Optional[date] = Query(None, description="Historical date (YYYY-MM-DD)"),
) -> list[PriceComparisonItem]:
    try:
        items = await get_part_price_comparison(
            db,
            garage_id=user.garage_id,
            part_public_id=part_public_id,
            at_date=at,
        )
    except PartNotFoundForPriceError:
        raise HTTPException(status_code=404, detail="Part not found")

    return [PriceComparisonItem(**item) for item in items]
