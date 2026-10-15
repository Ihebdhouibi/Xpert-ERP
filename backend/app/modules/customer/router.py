"""Customer module HTTP endpoints.

Wires the service layer to FastAPI. Permission gates come from the RBAC
dependency factory. The merge-prompt 409 response is returned as a raw
JSONResponse so the body shape matches `MergePromptResponse`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.models import AppUser
from app.modules.customer import repository as repo, service as svc
from app.modules.customer.models import (
    Customer,
    CustomerBalanceEvent,
    CustomerContact,
    CustomerStatus,
    CustomerType,
)
from app.modules.customer.schemas import (
    AddressSchema,
    CreditLimitUpdateRequest,
    CustomerBalanceEventListResponse,
    CustomerBalanceEventSummary,
    CustomerContactSummary,
    CustomerCreateRequest,
    CustomerDetail,
    CustomerImportResult,
    CustomerListResponse,
    CustomerQuickCreateRequest,
    CustomerSummary,
    CustomerUpdateRequest,
    MergePromptResponse,
    CustomerSpendingSummary,
)
from app.modules.rbac.dependencies import AuthUser, require_permission, require_role
from app.core.logging import get_logger

router = APIRouter(prefix="/customers", tags=["customers"])
logger = get_logger("customer.router")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_actor_user_id(
    db: AsyncSession, current_user_public_id: str
) -> Optional[int]:
    """Resolve JWT subject (public_id) → internal app_user.id for audit.

    Returns None if the lookup fails so audit still writes (with NULL user_id)
    instead of breaking the request.
    """
    import uuid as _uuid
    try:
        uid = _uuid.UUID(current_user_public_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(AppUser.id).where(AppUser.public_id == uid))
    row = result.first()
    return row[0] if row else None


def _request_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Request-ID")


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _to_summary(c: Customer) -> CustomerSummary:
    return CustomerSummary(
        id=str(c.public_id),
        int_id=c.id,
        garage_id=c.garage_id,
        type=c.type,
        full_name=c.full_name,
        company_name=c.company_name,
        email=c.email,
        phone_e164=c.phone_e164,
        status=c.status,
        segment=c.segment,
        credit_limit_minor=c.credit_limit_minor,
        credit_currency=c.credit_currency,
        outstanding_minor=c.outstanding_minor,
        last_visit_at=c.last_visit_at,
        created_at=c.created_at,
    )


def _to_detail(c: Customer) -> CustomerDetail:
    return CustomerDetail(
        id=str(c.public_id),
        int_id=c.id,
        garage_id=c.garage_id,
        type=c.type,
        full_name=c.full_name,
        company_name=c.company_name,
        email=c.email,
        phone_e164=c.phone_e164,
        status=c.status,
        segment=c.segment,
        credit_limit_minor=c.credit_limit_minor,
        credit_currency=c.credit_currency,
        outstanding_minor=c.outstanding_minor,
        last_visit_at=c.last_visit_at,
        created_at=c.created_at,
        fiscal_id=c.fiscal_id,
        address=c.address,
        loyalty_points=c.loyalty_points,
        notes=c.notes,
        version=c.version,
        updated_at=c.updated_at,
        contacts=[
            CustomerContactSummary(
                id=ct.id,
                channel=ct.channel,
                value=ct.value,
                label=ct.label,
                is_primary=ct.is_primary,
            )
            for ct in c.contacts
        ],
    )


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=CustomerListResponse,
    dependencies=[require_permission("customer.read")],
    summary="List / search customers in the current garage",
)
async def list_customers(
    user: AuthUser,
    q: Optional[str] = Query(None, max_length=100, description="Free-text search across name, company, phone, email, fiscal id"),
    status_: Optional[CustomerStatus] = Query(None, alias="status"),
    type_: Optional[CustomerType] = Query(None, alias="type"),
    segment: Optional[str] = Query(None, max_length=50),
    include_deleted: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CustomerListResponse:
    offset = (page - 1) * page_size
    rows = await repo.search(
        db, user.garage_id,
        q=q, status=status_, type_=type_, segment=segment,
        include_deleted=include_deleted,
        limit=page_size, offset=offset,
    )
    total = await repo.count_search(
        db, user.garage_id,
        q=q, status=status_, type_=type_, segment=segment,
        include_deleted=include_deleted,
    )
    return CustomerListResponse(
        items=[_to_summary(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/by-int-id/{int_id}",
    response_model=CustomerSummary,
    dependencies=[require_permission("customer.read")],
    summary="Resolve an internal integer customer ID to a summary (used by cross-module FKs)",
)
async def get_customer_by_int_id(
    int_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CustomerSummary:
    c = await repo.get_by_id(db, user.garage_id, int_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return _to_summary(c)


@router.get(
    "/{public_id}",
    response_model=CustomerDetail,
    dependencies=[require_permission("customer.read")],
    summary="Get a customer's full record including contacts",
)
async def get_customer(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    c = await repo.get_by_public_id(
        db, user.garage_id, public_id, with_contacts=True
    )
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return _to_detail(c)


@router.get(
    "/{public_id}/balance-events",
    response_model=CustomerBalanceEventListResponse,
    dependencies=[require_permission("customer.balance.read")],
    summary="List balance ledger events for a customer",
)
async def list_balance_events(
    public_id: str,
    user: AuthUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CustomerBalanceEventListResponse:
    c = await repo.get_by_public_id(db, user.garage_id, public_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    offset = (page - 1) * page_size
    items = await repo.list_balance_events(
        db, c.id, limit=page_size, offset=offset
    )
    total = await repo.count_balance_events(db, c.id)
    return CustomerBalanceEventListResponse(
        items=[CustomerBalanceEventSummary.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Mutating endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("customer.create")],
    summary="Create a customer; returns 409 with merge prompt on duplicate match",
    responses={
        201: {"model": CustomerDetail},
        409: {"model": MergePromptResponse, "description": "Duplicate detected — merge prompt"},
    },
)
async def create_customer(
    body: CustomerCreateRequest,
    user: AuthUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    actor_id = await _resolve_actor_user_id(db, user.public_id)
    result = await svc.create_customer(
        db,
        garage_id=user.garage_id,
        actor_user_id=actor_id,
        payload=body,
        request_id=_request_id(request),
        ip_address=_client_ip(request),
    )

    if isinstance(result, svc.DuplicateMatch):
        # Service rolled nothing forward; just return the prompt.
        prompt = MergePromptResponse(
            match_reason=result.reason,  # type: ignore[arg-type]
            existing=_to_summary(result.existing),
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=prompt.model_dump(mode="json"),
        )

    await db.commit()
    # Reload with contacts for the response.
    fresh = await repo.get_by_public_id(
        db, user.garage_id, str(result.public_id), with_contacts=True
    )
    assert fresh is not None
    return _to_detail(fresh)


@router.post(
    "/quick",
    status_code=status.HTTP_201_CREATED,
    response_model=CustomerDetail,
    dependencies=[require_permission("customer.create")],
    summary="Create a walk-in customer from just a name (no CIN/SIRET required)",
)
async def quick_create_customer(
    body: CustomerQuickCreateRequest,
    user: AuthUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    actor_id = await _resolve_actor_user_id(db, user.public_id)
    created = await svc.create_quick_customer(
        db,
        garage_id=user.garage_id,
        actor_user_id=actor_id,
        payload=body,
        request_id=_request_id(request),
        ip_address=_client_ip(request),
    )
    await db.commit()
    fresh = await repo.get_by_public_id(
        db, user.garage_id, str(created.public_id), with_contacts=True
    )
    assert fresh is not None
    return _to_detail(fresh)


_MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB
_XLSX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


@router.post(
    "/import",
    response_model=CustomerImportResult,
    dependencies=[require_permission("customer.create")],
    summary="Bulk import customers from an Excel (.xlsx) file",
)
async def import_customers(
    user: AuthUser,
    request: Request,
    file: UploadFile = File(..., description="Excel workbook with a header row"),
    db: AsyncSession = Depends(get_db),
) -> CustomerImportResult:
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Format non support\u00e9. Fournissez un fichier Excel (.xlsx).",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Fichier vide.")
    if len(content) > _MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Fichier trop volumineux (max 5 Mo).",
        )

    actor_id = await _resolve_actor_user_id(db, user.public_id)
    try:
        result = await svc.import_customers(
            db,
            garage_id=user.garage_id,
            actor_user_id=actor_id,
            content=content,
            request_id=_request_id(request),
            ip_address=_client_ip(request),
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    return result


@router.patch(
    "/{public_id}",
    response_model=CustomerDetail,
    dependencies=[require_permission("customer.update")],
    summary="Update a customer; requires the current version for optimistic locking",
)
async def update_customer(
    public_id: str,
    body: CustomerUpdateRequest,
    user: AuthUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    actor_id = await _resolve_actor_user_id(db, user.public_id)
    try:
        updated = await svc.update_customer(
            db,
            garage_id=user.garage_id,
            actor_user_id=actor_id,
            public_id=public_id,
            payload=body,
            request_id=_request_id(request),
            ip_address=_client_ip(request),
        )
    except svc.CustomerNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    except svc.OptimisticLockError as e:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "stale_version",
                "message": "Customer was modified by another user.",
                "expected_version": e.expected,
                "current_version": e.actual,
            },
        )
    except svc.FiscalIdConflictError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "fiscal_id_taken", "message": "This fiscal_id is already in use."},
        )
    except svc.InvalidFiscalIdError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_fiscal_id",
                "message": "fiscal_id must be a 14-digit SIRET number for company customers.",
            },
        )

    await db.commit()
    fresh = await repo.get_by_public_id(
        db, user.garage_id, public_id, with_contacts=True
    )
    assert fresh is not None
    return _to_detail(fresh)


@router.post(
    "/{public_id}/credit-limit",
    response_model=CustomerDetail,
    dependencies=[require_permission("customer.credit_limit.update")],
    summary="Update a customer's credit limit; requires an audit reason",
)
async def update_credit_limit(
    public_id: str,
    body: CreditLimitUpdateRequest,
    user: AuthUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    actor_id = await _resolve_actor_user_id(db, user.public_id)
    try:
        await svc.update_credit_limit(
            db,
            garage_id=user.garage_id,
            actor_user_id=actor_id,
            public_id=public_id,
            payload=body,
            request_id=_request_id(request),
            ip_address=_client_ip(request),
        )
    except svc.CustomerNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    await db.commit()
    fresh = await repo.get_by_public_id(
        db, user.garage_id, public_id, with_contacts=True
    )
    assert fresh is not None
    return _to_detail(fresh)


@router.delete(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[require_permission("customer.delete")],
    summary="Soft-delete a customer",
)
async def soft_delete_customer(
    public_id: str,
    user: AuthUser,
    request: Request,
    reason: Optional[str] = Query(None, max_length=500),
    db: AsyncSession = Depends(get_db),
) -> Response:
    actor_id = await _resolve_actor_user_id(db, user.public_id)
    try:
        await svc.soft_delete_customer(
            db,
            garage_id=user.garage_id,
            actor_user_id=actor_id,
            public_id=public_id,
            reason=reason,
            request_id=_request_id(request),
            ip_address=_client_ip(request),
        )
    except svc.CustomerNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{public_id}/restore",
    response_model=CustomerDetail,
    dependencies=[
        require_permission("customer.delete"),
        require_role("admin"),
    ],
    summary="Restore a soft-deleted customer (admin only)",
)
async def restore_customer(
    public_id: str,
    user: AuthUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    actor_id = await _resolve_actor_user_id(db, user.public_id)
    try:
        await svc.restore_customer(
            db,
            garage_id=user.garage_id,
            actor_user_id=actor_id,
            public_id=public_id,
            request_id=_request_id(request),
            ip_address=_client_ip(request),
        )
    except svc.CustomerNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    except svc.FiscalIdConflictError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "fiscal_id_taken_by_live_record",
                "message": "Cannot restore: another live customer holds this fiscal_id.",
            },
        )

    await db.commit()
    fresh = await repo.get_by_public_id(
        db, user.garage_id, public_id, with_contacts=True
    )
    assert fresh is not None
    return _to_detail(fresh)


# ---------------------------------------------------------------------------
# Customer-scoped sub-resource endpoints
# ---------------------------------------------------------------------------


async def _resolve_customer_by_public_id(
    db: AsyncSession, garage_id: int, public_id: str
) -> Customer:
    """Resolve a customer by public UUID, raising 404 if not found."""
    c = await repo.get_by_public_id(db, garage_id, public_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return c


@router.get(
    "/{public_id}/vehicles",
    dependencies=[require_permission("customer.read"), require_permission("vehicle.read")],
    summary="List all vehicles linked to this customer",
)
async def list_customer_vehicles(
    public_id: str,
    user: AuthUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.modules.vehicles import service as vehicle_service

    c = await _resolve_customer_by_public_id(db, user.garage_id, public_id)
    result = await vehicle_service.list_vehicles(
        db,
        garage_id=user.garage_id,
        search=None,
        customer_id=c.id,
        status=None,
        page=page,
        page_size=page_size,
    )
    return result.model_dump()


@router.get(
    "/{public_id}/repair-orders",
    dependencies=[require_permission("customer.read"), require_permission("repair_order.read")],
    summary="List all repair orders for this customer",
)
async def list_customer_repair_orders(
    public_id: str,
    user: AuthUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    vehicle_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.modules.repair_order.repository import RepairOrderRepository
    from app.modules.repair_order.models import ROStatus
    from app.modules.repair_order.schemas import RepairOrderSummary

    c = await _resolve_customer_by_public_id(db, user.garage_id, public_id)

    ro_status: Optional[ROStatus] = None
    if status_filter:
        try:
            ro_status = ROStatus(status_filter)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid status: {status_filter}")

    rows, total = await RepairOrderRepository.list(
        db,
        garage_id=user.garage_id,
        customer_id=c.id,
        vehicle_id=vehicle_id,
        status=ro_status,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [RepairOrderSummary.model_validate(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{public_id}/quotations",
    dependencies=[require_permission("customer.read"), require_permission("quotation.read")],
    summary="List all quotations for this customer",
)
async def list_customer_quotations(
    public_id: str,
    user: AuthUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.modules.quotation import service as quot_service
    from app.modules.quotation.models import QuotationStatus

    c = await _resolve_customer_by_public_id(db, user.garage_id, public_id)

    q_status: Optional[QuotationStatus] = None
    if status_filter:
        try:
            q_status = QuotationStatus(status_filter)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid status: {status_filter}")

    result = await quot_service.list_quotations(
        db,
        user.garage_id,
        customer_id=c.id,
        status=q_status,
        page=page,
        page_size=page_size,
    )
    return result.model_dump()


@router.get(
    "/{public_id}/invoices",
    dependencies=[require_permission("customer.read"), require_permission("invoice.read")],
    summary="List all invoices for this customer",
)
async def list_customer_invoices(
    public_id: str,
    user: AuthUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.modules.invoice import service as inv_service
    from app.modules.invoice.models import InvoiceStatus

    c = await _resolve_customer_by_public_id(db, user.garage_id, public_id)

    inv_status: Optional[InvoiceStatus] = None
    if status_filter:
        try:
            inv_status = InvoiceStatus(status_filter)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid status: {status_filter}")

    result = await inv_service.list_invoices(
        db,
        user.garage_id,
        customer_id=c.id,
        status=inv_status,
        page=page,
        page_size=page_size,
    )
    return result.model_dump()


@router.get(
    "/{public_id}/spending-summary",
    response_model=CustomerSpendingSummary,
    dependencies=[require_permission("customer.read"), require_permission("invoice.read")],
    summary="Aggregated spending statistics for this customer",
)
async def get_customer_spending_summary(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> CustomerSpendingSummary:
    from app.modules.invoice.models import Invoice, InvoiceStatus
    from app.modules.repair_order.models import RepairOrder, ROStatus
    from app.modules.advance_payment.models import AdvancePayment

    c = await _resolve_customer_by_public_id(db, user.garage_id, public_id)
    cid = c.id
    gid = user.garage_id

    now = datetime.now(tz=timezone.utc)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    # --- Invoice aggregates (exclude draft & cancelled) ---
    inv_row = (await db.execute(
        select(
            func.coalesce(func.sum(Invoice.total_minor), 0).label("total_invoiced"),
            func.coalesce(func.sum(Invoice.paid_amount_minor), 0).label("total_paid"),
            func.coalesce(func.sum(Invoice.outstanding_minor), 0).label("total_outstanding"),
        ).where(
            Invoice.garage_id == gid,
            Invoice.customer_id == cid,
            Invoice.deleted_at.is_(None),
            Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partial, InvoiceStatus.paid]),
        )
    )).one()

    # Current year invoiced
    inv_year_row = (await db.execute(
        select(
            func.coalesce(func.sum(Invoice.total_minor), 0).label("year_invoiced"),
        ).where(
            Invoice.garage_id == gid,
            Invoice.customer_id == cid,
            Invoice.deleted_at.is_(None),
            Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partial, InvoiceStatus.paid]),
            Invoice.issued_at >= year_start,
        )
    )).one()

    # --- Repair order counts ---
    ro_total = (await db.execute(
        select(func.count()).where(
            RepairOrder.garage_id == gid,
            RepairOrder.customer_id == cid,
            RepairOrder.deleted_at.is_(None),
        )
    )).scalar_one()

    ro_completed = (await db.execute(
        select(func.count()).where(
            RepairOrder.garage_id == gid,
            RepairOrder.customer_id == cid,
            RepairOrder.deleted_at.is_(None),
            RepairOrder.status == ROStatus.delivered,
        )
    )).scalar_one()

    last_ro_at = (await db.execute(
        select(RepairOrder.created_at).where(
            RepairOrder.garage_id == gid,
            RepairOrder.customer_id == cid,
            RepairOrder.deleted_at.is_(None),
        ).order_by(RepairOrder.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    # --- Unapplied advance payment balance ---
    adv_unapplied = (await db.execute(
        select(func.coalesce(func.sum(AdvancePayment.amount_minor), 0)).where(
            AdvancePayment.garage_id == gid,
            AdvancePayment.customer_id == cid,
            AdvancePayment.applied_to_invoice_id.is_(None),
        )
    )).scalar_one()

    return CustomerSpendingSummary(
        total_invoiced_minor=inv_row.total_invoiced,
        total_paid_minor=inv_row.total_paid,
        total_outstanding_minor=inv_row.total_outstanding,
        current_year_invoiced_minor=inv_year_row.year_invoiced,
        total_repair_orders=ro_total,
        completed_repair_orders=ro_completed,
        last_order_at=last_ro_at,
        advance_balance_minor=adv_unapplied,
        loyalty_points=c.loyalty_points,
    )


@router.get(
    "/{public_id}/delivery-notes",
    dependencies=[require_permission("customer.read"), require_permission("invoice.read")],
    summary="List all delivery notes for this customer",
)
async def list_customer_delivery_notes(
    public_id: str,
    user: AuthUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.modules.delivery_note import service as dn_service
    from app.modules.delivery_note.models import DeliveryNoteStatus

    c = await _resolve_customer_by_public_id(db, user.garage_id, public_id)

    dn_status: Optional[DeliveryNoteStatus] = None
    if status_filter:
        try:
            dn_status = DeliveryNoteStatus(status_filter)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid status: {status_filter}")

    result = await dn_service.list_delivery_notes(
        db,
        user.garage_id,
        customer_id=c.id,
        status=dn_status,
        page=page,
        page_size=page_size,
    )
    return result.model_dump()
