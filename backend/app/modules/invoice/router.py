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
    ConvertQuotationRequest,
    InvoiceCreateRequest,
    InvoiceFromDeliveryNotesRequest,
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
from app.modules.customer.credit_service import CreditLimitExceededError
from app.core.logging import get_logger

router = APIRouter(prefix="/invoices", tags=["invoices"])
logger = get_logger("invoice.router")

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
# Create invoice directly from a repair order
# ---------------------------------------------------------------------------

@router.post(
    "/from-repair-order/{ro_public_id}",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("invoice.create")],
    summary="Create a draft invoice pre-linked to a repair order",
)
async def create_invoice_from_repair_order(
    user: AuthUser,
    ro_public_id: str,
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    from app.modules.repair_order.repository import RepairOrderRepository
    ro = await RepairOrderRepository.get_by_public_id(
        db, garage_id=user.garage_id, public_id=ro_public_id, load_relationships=True
    )
    if not ro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair order not found.")

    from decimal import Decimal
    from app.modules.invoice.models import InvoiceLineKind

    lines: list[InvoiceLineCreateRequest] = []

    from app.core.constants import TVA_PCT

    # Labor lines → HT unit price + 20% VAT
    for ll in ro.labor_lines:
        lines.append(InvoiceLineCreateRequest(
            kind=InvoiceLineKind.labor,
            description=ll.labor_type,
            quantity=Decimal("1.000"),
            unit_price_minor=ll.rate_minor,
            discount_percent=Decimal("0"),
            vat_rate=TVA_PCT,
        ))

    # Part lines → HT unit price + remise + 20% VAT
    for pl in ro.part_lines:
        lines.append(InvoiceLineCreateRequest(
            kind=InvoiceLineKind.part,
            description=pl.part_name,
            quantity=Decimal(str(pl.quantity)),
            unit_price_minor=pl.unit_cost_minor,
            discount_percent=Decimal(str(pl.remise_pct)),
            vat_rate=TVA_PCT,
        ))

    request = InvoiceCreateRequest(
        customer_id=ro.customer_id,
        vehicle_id=ro.vehicle_id,
        repair_order_id=ro.id,
        notes=ro.notes,
        lines=lines,
    )
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
    body: ConvertQuotationRequest = Body(default_factory=ConvertQuotationRequest),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        return await service.convert_quotation(
            db, quotation_id, user.garage_id, due_at=body.due_at, user_id=user.user_id
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
# Create invoice from one or more delivery notes
# ---------------------------------------------------------------------------

@router.post(
    "/from-delivery-notes",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("invoice.create")],
    summary="Create a draft invoice aggregating lines from one or more delivery notes",
)
async def create_invoice_from_delivery_notes(
    user: AuthUser,
    request: InvoiceFromDeliveryNotesRequest,
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        return await service.create_invoice_from_delivery_notes(
            db, request=request, garage_id=user.garage_id, user_id=user.user_id
        )
    except InvoiceStateError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bon de livraison introuvable.")


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
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    try:
        return await service.get_invoice_by_public_id(db, invoice_id, user.garage_id)
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
    invoice_id: str,
    request: InvoiceUpdateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        return await service.update_invoice(
            db, inv.id, user.garage_id,
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
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        await service.delete_invoice(db, inv.id, user.garage_id, user_id=user.user_id)
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
    invoice_id: str,
    request: InvoiceLineCreateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        return await service.add_line(
            db, inv.id, user.garage_id,
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
    invoice_id: str,
    line_id: int,
    request: InvoiceLineUpdateRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        return await service.update_line(
            db, inv.id, line_id, user.garage_id,
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
    invoice_id: str,
    line_id: int,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        return await service.remove_line(
            db, inv.id, line_id, user.garage_id,
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
    invoice_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        return await service.issue_invoice(
            db, inv.id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CreditLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "credit_limit_exceeded",
                "customer_public_id": e.customer_public_id,
                "doc_type": "invoice",
                "outstanding": e.outstanding,
                "limit": e.limit,
                "additional": e.additional,
                "message": (
                    f"Limite de crédit dépassée. "
                    f"Encours : {e.outstanding / 100:.2f} €, "
                    f"Facture : {e.additional / 100:.2f} €, "
                    f"Limite : {e.limit / 100:.2f} €."
                ),
            },
        )


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceOut,
    dependencies=[require_permission("invoice.cancel")],
    summary="Cancel invoice (DRAFT/ISSUED → CANCELLED)",
)
async def cancel_invoice(
    user: AuthUser,
    invoice_id: str,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    version = _parse_if_match(if_match)
    try:
        inv = await service._resolve(db, invoice_id, user.garage_id)
        return await service.cancel_invoice(
            db, inv.id, user.garage_id, expected_version=version, user_id=user.user_id
        )
    except InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    except (InvoiceStateError, InvoiceVersionError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
