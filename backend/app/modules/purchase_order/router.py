from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.routing import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.purchase_order.models import PurchaseOrderStatus
from app.modules.purchase_order.repository import PurchaseOrderRepository
from app.modules.purchase_order.service import (
    POInvalidTransitionError,
    POLineNotFoundError,
    PONotFoundError,
    POVersionConflictError,
    PartNotFoundForPOError,
    SupplierNotFoundForPOError,
    cancel_po,
    create_po,
    create_po_from_alert,
    receive_po,
    send_po,
    update_invoiced_qty,
    update_po,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(tags=["purchase-orders"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class POLineInput(BaseModel):
    part_public_id: str
    quantity_ordered: int = Field(..., gt=0)
    unit_price_ht: int = Field(..., ge=0)


class POCreateRequest(BaseModel):
    supplier_public_id: str
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    lines: list[POLineInput] = Field(..., min_length=1)


class POUpdateRequest(BaseModel):
    version: int
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    lines: Optional[list[POLineInput]] = None


class POVersionRequest(BaseModel):
    version: int


class POReceiveLineInput(BaseModel):
    line_id: int
    quantity_received: int = Field(..., gt=0)


class POReceiveRequest(BaseModel):
    version: int
    lines: list[POReceiveLineInput] = Field(..., min_length=1)


class POInvoiceLineRequest(BaseModel):
    quantity_invoiced: int = Field(..., ge=0)


class POLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    quantity_ordered: int
    unit_price_ht: int
    quantity_received: int
    quantity_invoiced: int
    match_flag: str


class POSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supplier_id: int
    doc_number: Optional[str]
    status: str
    expected_delivery_date: Optional[date]
    notes: Optional[str]
    total_ht: int
    version: int
    created_at: datetime
    updated_at: datetime
    lines: list[POLineResponse]

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if hasattr(data, "public_id"):
            data.__dict__["id"] = str(data.public_id)
        return data


class POListResponse(BaseModel):
    items: list[POSummary]
    total: int
    page: int
    page_size: int


class POFromAlertRequest(BaseModel):
    supplier_public_id: str
    unit_price_ht: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/purchase-orders",
    response_model=POListResponse,
    dependencies=[require_permission("purchase_order.read")],
)
async def list_purchase_orders(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    status: Optional[PurchaseOrderStatus] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> POListResponse:
    items, total = await PurchaseOrderRepository.list(
        db,
        garage_id=user.garage_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return POListResponse(
        items=[POSummary.model_validate(po) for po in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/purchase-orders",
    status_code=http_status.HTTP_201_CREATED,
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.create")],
)
async def create_purchase_order(
    body: POCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    try:
        po = await create_po(
            db,
            garage_id=user.garage_id,
            supplier_public_id=body.supplier_public_id,
            lines_data=[ln.model_dump() for ln in body.lines],
            expected_delivery_date=body.expected_delivery_date,
            notes=body.notes,
        )
        await db.commit()
        await db.refresh(po, ["lines"])
        return POSummary.model_validate(po)
    except SupplierNotFoundForPOError:
        raise HTTPException(status_code=404, detail="Supplier not found")
    except PartNotFoundForPOError as e:
        raise HTTPException(status_code=404, detail=f"Part not found: {e}")
    except POInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/purchase-orders/{public_id}",
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.read")],
)
async def get_purchase_order(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    po = await PurchaseOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return POSummary.model_validate(po)


@router.put(
    "/purchase-orders/{public_id}",
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.create")],
)
async def update_purchase_order(
    public_id: str,
    body: POUpdateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    try:
        po = await update_po(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            submitted_version=body.version,
            lines_data=[ln.model_dump() for ln in body.lines] if body.lines is not None else None,
            expected_delivery_date=body.expected_delivery_date,
            notes=body.notes,
        )
        await db.commit()
        await db.refresh(po, ["lines"])
        return POSummary.model_validate(po)
    except PONotFoundError:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    except POVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "current_version": e.current_version,
                "submitted_version": e.submitted_version,
            },
        )
    except POInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PartNotFoundForPOError as e:
        raise HTTPException(status_code=404, detail=f"Part not found: {e}")


@router.post(
    "/purchase-orders/{public_id}/send",
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.send")],
)
async def send_purchase_order(
    public_id: str,
    body: POVersionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    try:
        po = await send_po(db, user.garage_id, public_id, body.version)
        await db.commit()
        await db.refresh(po, ["lines"])
        return POSummary.model_validate(po)
    except PONotFoundError:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    except POVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except POInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/purchase-orders/{public_id}/receive",
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.reception.record")],
)
async def receive_purchase_order(
    public_id: str,
    body: POReceiveRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    try:
        po = await receive_po(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            submitted_version=body.version,
            lines=[ln.model_dump() for ln in body.lines],
            user_id=user.user_id,
        )
        await db.commit()
        await db.refresh(po, ["lines"])
        return POSummary.model_validate(po)
    except PONotFoundError:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    except POVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except POInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except POLineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/purchase-orders/{public_id}/cancel",
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.create")],
)
async def cancel_purchase_order(
    public_id: str,
    body: POVersionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    try:
        po = await cancel_po(db, user.garage_id, public_id, body.version)
        await db.commit()
        await db.refresh(po, ["lines"])
        return POSummary.model_validate(po)
    except PONotFoundError:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    except POVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except POInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch(
    "/purchase-orders/{public_id}/lines/{line_id}/invoice",
    response_model=POLineResponse,
    dependencies=[require_permission("purchase_order.reception.record")],
)
async def update_line_invoiced_qty(
    public_id: str,
    line_id: int,
    body: POInvoiceLineRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POLineResponse:
    try:
        line = await update_invoiced_qty(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            line_id=line_id,
            quantity_invoiced=body.quantity_invoiced,
        )
        await db.commit()
        return POLineResponse.model_validate(line)
    except PONotFoundError:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    except POLineNotFoundError:
        raise HTTPException(status_code=404, detail="Line not found")


@router.post(
    "/stock/alerts/{alert_id}/create-po",
    status_code=http_status.HTTP_201_CREATED,
    response_model=POSummary,
    dependencies=[require_permission("purchase_order.create")],
)
async def create_po_from_low_stock_alert(
    alert_id: int,
    body: POFromAlertRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> POSummary:
    try:
        po = await create_po_from_alert(
            db,
            garage_id=user.garage_id,
            alert_id=alert_id,
            supplier_public_id=body.supplier_public_id,
            unit_price_ht=body.unit_price_ht,
            user_id=user.user_id,
        )
        await db.commit()
        await db.refresh(po, ["lines"])
        return POSummary.model_validate(po)
    except PONotFoundError:
        raise HTTPException(status_code=404, detail="Alert not found")
    except SupplierNotFoundForPOError:
        raise HTTPException(status_code=404, detail="Supplier not found")
    except PartNotFoundForPOError:
        raise HTTPException(status_code=404, detail="Part not found")
