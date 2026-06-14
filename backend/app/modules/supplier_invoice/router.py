from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import Response
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
    po_line_id: Optional[int] = None
    part_public_id: Optional[str] = None
    description: str = ""
    quantity: int = Field(..., gt=0)
    unit_price_ht: int = Field(..., ge=0)
    vat_rate: float = Field(20.0, ge=0, le=100)

    @model_validator(mode="after")
    def check_line_reference(self) -> "SILineInput":
        if self.po_line_id is None and not self.part_public_id:
            raise ValueError("Either po_line_id or part_public_id must be provided")
        return self


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
    supplier_id: int
    purchase_order_id: int
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
    "/supplier-invoices/accounting-export-csv",
    response_class=Response,
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV journal des achats"},
    },
    dependencies=[require_permission("supplier_invoice.read")],
)
async def export_paid_invoices_csv(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a semicolon-separated CSV of all paid supplier invoices journal entries."""
    import csv
    import io
    from fastapi.responses import Response as FastAPIResponse
    from sqlalchemy import select as sa_select
    from app.modules.supplier.models import Supplier

    items, _ = await SupplierInvoiceRepository.list(
        db,
        garage_id=user.garage_id,
        status=SupplierInvoiceStatus.paid,
        page=1,
        page_size=10_000,
    )

    supplier_ids = list({si.supplier_id for si in items})
    suppliers_map: dict[int, str] = {}
    if supplier_ids:
        sup_res = await db.execute(sa_select(Supplier).where(Supplier.id.in_(supplier_ids)))
        suppliers_map = {s.id: s.name for s in sup_res.scalars()}

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["N° Facture", "Date", "Échéance", "Fournisseur", "Compte", "Libellé", "Débit (€)", "Crédit (€)"])

    for si in items:
        supplier_name = suppliers_map.get(si.supplier_id, "—")
        date_str = si.received_at.date().isoformat() if si.received_at else ""
        due_str = si.due_date.isoformat() if si.due_date else ""
        total_ht = si.total_ht / 100
        total_ttc = si.total_ttc / 100
        tva = (si.total_ttc - si.total_ht) / 100

        writer.writerow([si.number, date_str, due_str, supplier_name, "607", "Achats de marchandises", f"{total_ht:.2f}", ""])
        writer.writerow([si.number, date_str, due_str, supplier_name, "44566", "TVA déductible", f"{tva:.2f}", ""])
        writer.writerow([si.number, date_str, due_str, supplier_name, "401", "Fournisseurs", "", f"{total_ttc:.2f}"])

    # UTF-8 BOM so Excel opens it correctly without import wizard
    csv_bytes = "﻿".encode("utf-8") + output.getvalue().encode("utf-8")
    return FastAPIResponse(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="export-comptable-fournisseurs.csv"'},
    )


@router.get(
    "/supplier-invoices/accounting-export-pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF journal des achats"},
    },
    dependencies=[require_permission("supplier_invoice.read")],
)
async def export_paid_invoices_pdf(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a PDF of all paid supplier invoices journal entries."""
    import asyncio
    from datetime import date as _date
    from pathlib import Path
    from fastapi.responses import Response as FastAPIResponse
    from sqlalchemy import select as sa_select
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from app.modules.supplier.models import Supplier
    from app.core.config import get_settings

    items, _ = await SupplierInvoiceRepository.list(
        db,
        garage_id=user.garage_id,
        status=SupplierInvoiceStatus.paid,
        page=1,
        page_size=10_000,
    )

    supplier_ids = list({si.supplier_id for si in items})
    suppliers_map: dict[int, str] = {}
    if supplier_ids:
        sup_res = await db.execute(sa_select(Supplier).where(Supplier.id.in_(supplier_ids)))
        suppliers_map = {s.id: s.name for s in sup_res.scalars()}

    rows = []
    sum_ht = 0.0
    sum_tva = 0.0
    sum_ttc = 0.0
    invoice_numbers: set[str] = set()

    for si in items:
        supplier_name = suppliers_map.get(si.supplier_id, "—")
        date_str = si.received_at.date().strftime("%d/%m/%Y") if si.received_at else "—"
        due_str = si.due_date.strftime("%d/%m/%Y") if si.due_date else "—"
        ht = si.total_ht / 100
        ttc = si.total_ttc / 100
        tva = (si.total_ttc - si.total_ht) / 100
        sum_ht += ht
        sum_tva += tva
        sum_ttc += ttc
        invoice_numbers.add(si.number)

        rows.append({"number": si.number, "date": date_str, "due": due_str, "supplier": supplier_name,
                     "account": "607", "label": "Achats de marchandises", "debit": f"{ht:.2f}", "credit": ""})
        rows.append({"number": si.number, "date": date_str, "due": due_str, "supplier": supplier_name,
                     "account": "44566", "label": "TVA déductible", "debit": f"{tva:.2f}", "credit": ""})
        rows.append({"number": si.number, "date": date_str, "due": due_str, "supplier": supplier_name,
                     "account": "401", "label": "Fournisseurs", "debit": "", "credit": f"{ttc:.2f}"})

    settings = get_settings()
    templates_dir = Path(__file__).parent.parent.parent.parent / "templates" / "documents"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(["html"]))

    html_string = env.get_template("si_accounting_export.html").render(
        rows=rows,
        export_date=_date.today().strftime("%d/%m/%Y"),
        invoice_count=len(invoice_numbers),
        total_ht=f"{sum_ht:.2f}",
        total_tva=f"{sum_tva:.2f}",
        total_ttc=f"{sum_ttc:.2f}",
        garage_name=settings.pdf_garage_name,
        garage_address=getattr(settings, "pdf_garage_address", ""),
        garage_phone=getattr(settings, "pdf_garage_phone", ""),
        garage_email=getattr(settings, "pdf_garage_email", ""),
        garage_logo_path=getattr(settings, "pdf_garage_logo_path", ""),
        vat_number=getattr(settings, "pdf_vat_number", ""),
        footer_text=getattr(settings, "pdf_footer_text", ""),
    )

    def _render() -> bytes:
        from weasyprint import HTML
        return HTML(string=html_string, base_url=str(templates_dir) + "/").write_pdf()

    loop = asyncio.get_event_loop()
    pdf_bytes: bytes = await loop.run_in_executor(None, _render)

    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="export-comptable-fournisseurs.pdf"'},
    )


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
