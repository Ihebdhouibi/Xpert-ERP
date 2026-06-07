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
from app.modules.supplier_invoice.models import SupplierInvoiceStatus
from app.modules.supplier_invoice.repository import SupplierInvoiceRepository
from app.modules.supplier_invoice.service import (
    SIDiscrepancyBlocksApprovalError,
    SIInvalidTransitionError,
    SINotFoundError,
    SIPOLineMissingError,
    SIPONotFoundError,
    SISupplierNotFoundError,
    SIVersionConflictError,
    approve_supplier_invoice,
    build_accounting_export,
    cancel_supplier_invoice,
    create_supplier_invoice,
    mark_paid,
    override_discrepancy,
    post_supplier_invoice,
    update_supplier_invoice,
)
from app.core.logging import get_logger

router = APIRouter(tags=["supplier-invoices"])
logger = get_logger("supplier_invoice.router")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SILineInput(BaseModel):
    po_line_id: int
    description: str = ""
    quantity: int = Field(..., gt=0)
    unit_price_ht: int = Field(..., ge=0)
    vat_rate: float = Field(20.0, ge=0, le=100)


class SICreateRequest(BaseModel):
    supplier_public_id: str
    po_public_id: str
    number: str = Field(..., min_length=1)
    lines: list[SILineInput] = Field(..., min_length=1)
    received_at: Optional[datetime] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


class SIUpdateRequest(BaseModel):
    version: int
    number: Optional[str] = None
    lines: Optional[list[SILineInput]] = None
    received_at: Optional[datetime] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


class SIVersionRequest(BaseModel):
    version: int


class SIOverrideRequest(BaseModel):
    version: int
    reason: str = Field(..., min_length=1)


class SILineOut(BaseModel):
    po_line_id: int
    description: str
    quantity: int
    unit_price_ht: int
    vat_rate: float
    line_total_ht: int
    line_total_ttc: int
    match_status: str
    po_quantity_ordered: int
    po_quantity_received: int
    po_unit_price_ht: int


class SISummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supplier_id: Optional[int]
    purchase_order_id: Optional[int]
    number: str
    status: str
    lines: list[dict[str, Any]]
    total_ht: int
    total_ttc: int
    has_discrepancy: bool
    override_reason: Optional[str]
    received_at: Optional[datetime]
    due_date: Optional[date]
    notes: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if hasattr(data, "public_id"):
            data.__dict__["id"] = str(data.public_id)
        return data


class SIListResponse(BaseModel):
    items: list[SISummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/supplier-invoices",
    response_model=SIListResponse,
    dependencies=[require_permission("supplier_invoice.read")],
)
async def list_supplier_invoices(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    status: Optional[SupplierInvoiceStatus] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SIListResponse:
    items, total = await SupplierInvoiceRepository.list(
        db,
        garage_id=user.garage_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return SIListResponse(
        items=[SISummary.model_validate(si) for si in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/supplier-invoices",
    status_code=http_status.HTTP_201_CREATED,
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.create")],
)
async def create_supplier_invoice_endpoint(
    body: SICreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    try:
        si = await create_supplier_invoice(
            db,
            garage_id=user.garage_id,
            supplier_public_id=body.supplier_public_id,
            po_public_id=body.po_public_id,
            number=body.number,
            lines_data=[ln.model_dump() for ln in body.lines],
            received_at=body.received_at,
            due_date=body.due_date,
            notes=body.notes,
            user_id=user.user_id,
        )
        await db.commit()
        return SISummary.model_validate(si)
    except SISupplierNotFoundError:
        raise HTTPException(status_code=404, detail="Supplier not found")
    except SIPONotFoundError:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    except SIPOLineMissingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/supplier-invoices/{public_id}",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.read")],
)
async def get_supplier_invoice(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    si = await SupplierInvoiceRepository.get_by_public_id(db, user.garage_id, public_id)
    if not si:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    return SISummary.model_validate(si)


@router.put(
    "/supplier-invoices/{public_id}",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.create")],
)
async def update_supplier_invoice_endpoint(
    public_id: str,
    body: SIUpdateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    try:
        si = await update_supplier_invoice(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            submitted_version=body.version,
            lines_data=[ln.model_dump() for ln in body.lines] if body.lines is not None else None,
            number=body.number,
            received_at=body.received_at,
            due_date=body.due_date,
            notes=body.notes,
        )
        await db.commit()
        return SISummary.model_validate(si)
    except SINotFoundError:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    except SIVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "current_version": e.current_version,
                "submitted_version": e.submitted_version,
            },
        )
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except (SIPOLineMissingError, SIPONotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/supplier-invoices/{public_id}/post",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.post")],
)
async def post_supplier_invoice_endpoint(
    public_id: str,
    body: SIVersionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    """Run three-way match and lock the invoice as posted."""
    try:
        si = await post_supplier_invoice(
            db, user.garage_id, public_id, body.version
        )
        await db.commit()
        return SISummary.model_validate(si)
    except SINotFoundError:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    except SIVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/supplier-invoices/{public_id}/override",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.override")],
)
async def override_supplier_invoice_discrepancy(
    public_id: str,
    body: SIOverrideRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    """Override discrepancy with a mandatory reason; produces an audit entry."""
    try:
        si = await override_discrepancy(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            submitted_version=body.version,
            reason=body.reason,
            user_id=user.user_id,
        )
        await db.commit()
        return SISummary.model_validate(si)
    except SINotFoundError:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    except SIVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/supplier-invoices/{public_id}/approve",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.approve")],
)
async def approve_supplier_invoice_endpoint(
    public_id: str,
    body: SIVersionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    try:
        si = await approve_supplier_invoice(
            db, user.garage_id, public_id, body.version
        )
        await db.commit()
        return SISummary.model_validate(si)
    except SINotFoundError:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    except SIVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except SIDiscrepancyBlocksApprovalError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/supplier-invoices/{public_id}/mark-paid",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.approve")],
)
async def mark_supplier_invoice_paid(
    public_id: str,
    body: SIVersionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    try:
        si = await mark_paid(db, user.garage_id, public_id, body.version)
        await db.commit()
        return SISummary.model_validate(si)
    except SINotFoundError:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    except SIVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/supplier-invoices/{public_id}/cancel",
    response_model=SISummary,
    dependencies=[require_permission("supplier_invoice.create")],
)
async def cancel_supplier_invoice_endpoint(
    public_id: str,
    body: SIVersionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SISummary:
    try:
        si = await cancel_supplier_invoice(db, user.garage_id, public_id, body.version)
        await db.commit()
        return SISummary.model_validate(si)
    except SINotFoundError:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    except SIVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "current_version": e.current_version},
        )
    except SIInvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/supplier-invoices/{public_id}/accounting-export",
    dependencies=[require_permission("supplier_invoice.read")],
)
async def get_accounting_export(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a purchases-journal entry structure for the supplier invoice."""
    si = await SupplierInvoiceRepository.get_by_public_id(db, user.garage_id, public_id)
    if not si:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    if si.status not in (SupplierInvoiceStatus.approved, SupplierInvoiceStatus.paid):
        raise HTTPException(
            status_code=422,
            detail="Accounting export is only available for approved or paid invoices",
        )
    return build_accounting_export(si)
