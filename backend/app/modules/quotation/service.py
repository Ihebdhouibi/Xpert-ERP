"""Quotation service — business logic, VAT + discount calculations."""
from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.quotation import repository as repo
from app.modules.quotation.models import (
    LineKind,
    Quotation,
    QuotationLine,
    QuotationStatus,
)
from app.modules.quotation.schemas import (
    QuotationCreateRequest,
    QuotationLineCreateRequest,
    QuotationLineOut,
    QuotationLineUpdateRequest,
    QuotationOut,
    QuotationUpdateRequest,
    QuotationListResponse,
)
from app.modules.sequence import service as seq_service
from app.modules.customer import repository as customer_repo

logger = get_logger("quotation.service")


async def _to_out(db: AsyncSession, quotation: Quotation) -> QuotationOut:
    """Build QuotationOut, enriching with customer name + repair-order public id."""
    out = QuotationOut.model_validate(quotation)
    if quotation.customer_id is not None:
        customer = await customer_repo.get_by_id(db, quotation.garage_id, quotation.customer_id)
        if customer:
            out.customer_name = (
                f"{customer.full_name} ({customer.company_name})"
                if customer.company_name
                else customer.full_name
            )
    if quotation.repair_order_id is not None:
        from sqlalchemy import select as _select
        from app.modules.repair_order.models import RepairOrder

        pub = (
            await db.execute(
                _select(RepairOrder.public_id).where(RepairOrder.id == quotation.repair_order_id)
            )
        ).scalar_one_or_none()
        if pub is not None:
            out.repair_order_public_id = str(pub)
    return out


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class QuotationNotFoundError(Exception):
    pass


class QuotationLineNotFoundError(Exception):
    pass


class QuotationStateError(Exception):
    """Raised when a status transition is illegal."""
    pass


class QuotationVersionError(Exception):
    """Raised on optimistic concurrency mismatch."""
    pass


# ---------------------------------------------------------------------------
# Money calculation helpers
# ---------------------------------------------------------------------------

def _compute_line_total(
    unit_price_minor: int,
    quantity: Decimal,
    discount_percent: Decimal,
) -> int:
    """Discounted line total in minor units (before VAT)."""
    gross = Decimal(unit_price_minor) * quantity
    total = gross * (Decimal("1") - discount_percent / Decimal("100"))
    return int(total.to_integral_value(rounding=ROUND_HALF_UP))


def _compute_line_vat(line_total_minor: int, vat_rate: Decimal) -> int:
    """VAT amount on a single line in minor units."""
    vat = Decimal(line_total_minor) * vat_rate / Decimal("100")
    return int(vat.to_integral_value(rounding=ROUND_HALF_UP))


def _recalculate_totals(quotation: Quotation) -> None:
    """Re-derive subtotal, discount, VAT and grand total from current lines."""
    subtotal = 0
    gross_total = 0
    vat_total = 0

    for line in quotation.lines:
        gross = int(
            (Decimal(line.unit_price_minor) * line.quantity).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )
        line_total = _compute_line_total(line.unit_price_minor, line.quantity, line.discount_percent)
        line_vat = _compute_line_vat(line_total, line.vat_rate)

        line.line_total_minor = line_total
        gross_total += gross
        subtotal += line_total
        vat_total += line_vat

    quotation.subtotal_minor = subtotal
    quotation.discount_minor = gross_total - subtotal  # total discount given
    quotation.vat_minor = vat_total
    quotation.total_minor = subtotal + vat_total


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_quotation(
    db: AsyncSession,
    *,
    request: QuotationCreateRequest,
    garage_id: int,
    user_id: int,
) -> QuotationOut:
    logger.info("create_quotation_start", garage_id=garage_id, user_id=user_id)
    quotation = Quotation(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        customer_id=request.customer_id,
        vehicle_id=request.vehicle_id,
        repair_order_id=request.repair_order_id,
        currency=request.currency.upper(),
        valid_until=request.valid_until,
        notes=request.notes,
        status=QuotationStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )

    # Build lines without yet assigning IDs
    for line_req in request.lines:
        line = _build_line(quotation, line_req)
        quotation.lines.append(line)

    _recalculate_totals(quotation)
    await repo.create(db, quotation)
    await db.commit()

    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("quotation_created", quotation_id=quotation.id, garage_id=garage_id)
    return QuotationOut.model_validate(fresh)


async def get_quotation(db: AsyncSession, quotation_id: int, garage_id: int) -> QuotationOut:
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    return await _to_out(db, quotation)


async def get_quotation_by_public_id(db: AsyncSession, public_id: str, garage_id: int) -> QuotationOut:
    quotation = await repo.get_by_public_id(db, public_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(public_id)
    return await _to_out(db, quotation)


async def _resolve(db: AsyncSession, public_id: str, garage_id: int) -> Quotation:
    """Resolve a public_id to a Quotation ORM object."""
    quotation = await repo.get_by_public_id(db, public_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(public_id)
    return quotation


async def list_quotations(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[QuotationStatus] = None,
    page: int = 1,
    page_size: int = 25,
) -> QuotationListResponse:
    items, total = await repo.list_quotations(
        db, garage_id, customer_id=customer_id, status=status, page=page, page_size=page_size
    )
    return QuotationListResponse(
        items=[await _to_out(db, q) for q in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_quotation(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    request: QuotationUpdateRequest,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("update_quotation_start", quotation_id=quotation_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.draft:
        raise QuotationStateError("Only draft quotations can be updated.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    if request.vehicle_id is not None:
        quotation.vehicle_id = request.vehicle_id
    if request.repair_order_id is not None:
        quotation.repair_order_id = request.repair_order_id
    if request.currency is not None:
        quotation.currency = request.currency.upper()
    if request.valid_until is not None:
        quotation.valid_until = request.valid_until
    if request.notes is not None:
        quotation.notes = request.notes

    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("update_quotation_success", quotation_id=quotation_id, garage_id=garage_id)
    return QuotationOut.model_validate(fresh)


async def delete_quotation(
    db: AsyncSession, quotation_id: int, garage_id: int, *, user_id: int
) -> None:
    logger.info("delete_quotation_start", quotation_id=quotation_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status not in (QuotationStatus.draft, QuotationStatus.rejected):
        raise QuotationStateError("Only draft or rejected quotations can be deleted.")
    await repo.soft_delete(db, quotation, deleted_by=user_id)
    await db.commit()
    logger.info("delete_quotation_success", quotation_id=quotation_id, garage_id=garage_id)


# ---------------------------------------------------------------------------
# Line management
# ---------------------------------------------------------------------------

def _build_line(quotation: Quotation, req: QuotationLineCreateRequest) -> QuotationLine:
    from app.core.constants import TVA_PCT
    line_total = _compute_line_total(req.unit_price_minor, req.quantity, req.discount_percent)
    return QuotationLine(
        quotation_id=quotation.id or 0,  # FK set by relationship
        kind=req.kind,
        part_id=req.part_id,
        description=req.description,
        quantity=req.quantity,
        unit_price_minor=req.unit_price_minor,
        discount_percent=req.discount_percent,
        vat_rate=TVA_PCT,
        line_total_minor=line_total,
    )


async def add_line(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    request: QuotationLineCreateRequest,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("add_line_start", quotation_id=quotation_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.draft:
        raise QuotationStateError("Lines can only be modified on draft quotations.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    from app.core.constants import TVA_PCT
    line = QuotationLine(
        quotation_id=quotation.id,
        kind=request.kind,
        part_id=request.part_id,
        description=request.description,
        quantity=request.quantity,
        unit_price_minor=request.unit_price_minor,
        discount_percent=request.discount_percent,
        vat_rate=TVA_PCT,
        line_total_minor=0,
    )
    await repo.add_line(db, line)
    quotation.lines.append(line)
    _recalculate_totals(quotation)
    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("add_line_success", quotation_id=quotation_id, garage_id=garage_id)
    return QuotationOut.model_validate(fresh)


async def update_line(
    db: AsyncSession,
    quotation_id: int,
    line_id: int,
    garage_id: int,
    *,
    request: QuotationLineUpdateRequest,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("update_line_start", quotation_id=quotation_id, line_id=line_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.draft:
        raise QuotationStateError("Lines can only be modified on draft quotations.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    line = await repo.get_line(db, line_id, quotation_id)
    if not line:
        raise QuotationLineNotFoundError(line_id)

    if request.kind is not None:
        line.kind = request.kind
    if request.part_id is not None:
        line.part_id = request.part_id
    if request.description is not None:
        line.description = request.description
    if request.quantity is not None:
        line.quantity = request.quantity
    if request.unit_price_minor is not None:
        line.unit_price_minor = request.unit_price_minor
    if request.discount_percent is not None:
        line.discount_percent = request.discount_percent
    if request.vat_rate is not None:
        line.vat_rate = request.vat_rate

    _recalculate_totals(quotation)
    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("update_line_success", quotation_id=quotation_id, line_id=line_id, garage_id=garage_id)
    return QuotationOut.model_validate(fresh)


async def remove_line(
    db: AsyncSession,
    quotation_id: int,
    line_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("remove_line_start", quotation_id=quotation_id, line_id=line_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.draft:
        raise QuotationStateError("Lines can only be modified on draft quotations.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    line = await repo.get_line(db, line_id, quotation_id)
    if not line:
        raise QuotationLineNotFoundError(line_id)

    quotation.lines = [l for l in quotation.lines if l.id != line_id]
    await repo.delete_line(db, line)
    _recalculate_totals(quotation)
    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("remove_line_success", quotation_id=quotation_id, line_id=line_id, garage_id=garage_id)
    return QuotationOut.model_validate(fresh)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

async def send_quotation(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("send_quotation_start", quotation_id=quotation_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.draft:
        raise QuotationStateError(f"Cannot send a quotation in status '{quotation.status.value}'.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    # Assign document number via sequence service
    seq = await seq_service.next(db, garage_id=garage_id, doc_type="QUOT")
    quotation.doc_number = seq.formatted
    quotation.status = QuotationStatus.sent
    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("quotation_sent", quotation_id=quotation_id, doc_number=fresh.doc_number if fresh else None)
    return QuotationOut.model_validate(fresh)


async def approve_quotation(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("approve_quotation_start", quotation_id=quotation_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.sent:
        raise QuotationStateError(f"Cannot approve a quotation in status '{quotation.status.value}'.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    quotation.status = QuotationStatus.approved
    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("quotation_approved", quotation_id=quotation_id)
    return QuotationOut.model_validate(fresh)


async def reject_quotation(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> QuotationOut:
    logger.info("reject_quotation_start", quotation_id=quotation_id, garage_id=garage_id)
    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status != QuotationStatus.sent:
        raise QuotationStateError(f"Cannot reject a quotation in status '{quotation.status.value}'.")
    if quotation.version != expected_version:
        raise QuotationVersionError(f"Version mismatch: expected {expected_version}, got {quotation.version}")

    quotation.status = QuotationStatus.rejected
    quotation.version += 1
    quotation.updated_by = user_id
    await repo.save(db, quotation)
    await db.commit()
    fresh = await repo.get_by_id(db, quotation.id, garage_id)
    logger.info("quotation_rejected", quotation_id=quotation_id)
    return QuotationOut.model_validate(fresh)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

async def send_quotation_email(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    recipient: str,
) -> None:
    """Email the quotation PDF to the client (customer.email) or to the configured admin address(es)."""
    from app.core.config import get_settings
    from app.modules.notification.adapter import EmailAttachment
    from app.modules.notification.service import dispatch, get_admin_recipients
    from app.modules.pdf import service as pdf_service

    quotation = await repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise QuotationNotFoundError(quotation_id)
    if quotation.status == QuotationStatus.draft:
        raise QuotationStateError("Le devis doit être envoyé avant l'envoi par email.")

    customer = (
        await customer_repo.get_by_id(db, garage_id, quotation.customer_id)
        if quotation.customer_id else None
    )
    settings = get_settings()

    if recipient == "client":
        if not customer or not customer.email:
            raise QuotationStateError("Le client n'a pas d'adresse email renseignée.")
        to_addresses = [customer.email]
        template_code = "quotation_send_client"
    else:
        to_addresses = get_admin_recipients()
        if not to_addresses:
            raise QuotationStateError("Aucune adresse email admin n'est configurée.")
        template_code = "quotation_send_admin"

    pdf_bytes = await pdf_service.render_quotation_pdf(db, quotation_id=quotation.id, garage_id=garage_id)
    filename = f"{quotation.doc_number or quotation.id}.pdf"
    context = {
        "customer_name": customer.full_name if customer else "",
        "quotation_number": quotation.doc_number or str(quotation.id),
        "total": f"{quotation.total_minor / 100:.2f}",
        "garage_name": settings.pdf_garage_name,
        "garage_phone": settings.pdf_garage_phone,
    }

    for addr in to_addresses:
        await dispatch(
            db,
            garage_id=garage_id,
            recipient_id=customer.id if recipient == "client" and customer else None,
            recipient=addr,
            channel="email",
            template_code=template_code,
            context=context,
            attachments=[EmailAttachment(filename=filename, content=pdf_bytes, mimetype="application/pdf")],
            respect_quiet_hours=False,
        )
