"""Invoice service — business logic, conversion from quotation, status transitions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.invoice import repository as repo
from app.modules.invoice.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceLineKind
from app.modules.invoice.schemas import (
    InvoiceCreateRequest,
    InvoiceLineCreateRequest,
    InvoiceLineUpdateRequest,
    InvoiceOut,
    InvoiceUpdateRequest,
    InvoiceListResponse,
)
from app.modules.sequence import service as seq_service

logger = get_logger("invoice.service")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InvoiceNotFoundError(Exception):
    pass


class InvoiceLineNotFoundError(Exception):
    pass


class InvoiceStateError(Exception):
    pass


class InvoiceVersionError(Exception):
    pass


class QuotationAlreadyConvertedError(Exception):
    pass


# ---------------------------------------------------------------------------
# Money helpers (identical logic to quotation)
# ---------------------------------------------------------------------------

def _line_total(unit_price_minor: int, quantity: Decimal, discount_percent: Decimal) -> int:
    gross = Decimal(unit_price_minor) * quantity
    total = gross * (Decimal("1") - discount_percent / Decimal("100"))
    return int(total.to_integral_value(rounding=ROUND_HALF_UP))


def _line_vat(line_total_minor: int, vat_rate: Decimal) -> int:
    vat = Decimal(line_total_minor) * vat_rate / Decimal("100")
    return int(vat.to_integral_value(rounding=ROUND_HALF_UP))


def _recalculate_totals(invoice: Invoice) -> None:
    subtotal = gross_total = vat_total = 0
    for line in invoice.lines:
        gross = int(
            (Decimal(line.unit_price_minor) * line.quantity).to_integral_value(rounding=ROUND_HALF_UP)
        )
        lt = _line_total(line.unit_price_minor, line.quantity, line.discount_percent)
        lv = _line_vat(lt, line.vat_rate)
        line.line_total_minor = lt
        gross_total += gross
        subtotal += lt
        vat_total += lv

    invoice.subtotal_minor = subtotal
    invoice.discount_minor = gross_total - subtotal
    invoice.vat_minor = vat_total
    invoice.total_minor = subtotal + vat_total
    paid = invoice.paid_amount_minor if invoice.paid_amount_minor is not None else 0
    invoice.outstanding_minor = invoice.total_minor - paid


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_invoice(
    db: AsyncSession,
    *,
    request: InvoiceCreateRequest,
    garage_id: int,
    user_id: int,
) -> InvoiceOut:
    invoice = Invoice(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        customer_id=request.customer_id,
        vehicle_id=request.vehicle_id,
        repair_order_id=request.repair_order_id,
        currency=request.currency.upper(),
        due_at=request.due_at,
        notes=request.notes,
        status=InvoiceStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )
    for line_req in request.lines:
        invoice.lines.append(_build_line(invoice, line_req))

    _recalculate_totals(invoice)
    await repo.create(db, invoice)
    await db.commit()

    fresh = await repo.get_by_id(db, invoice.id, garage_id)
    logger.info("invoice_created", invoice_id=invoice.id, garage_id=garage_id)
    return InvoiceOut.model_validate(fresh)


async def get_invoice(db: AsyncSession, invoice_id: int, garage_id: int) -> InvoiceOut:
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    return InvoiceOut.model_validate(inv)


async def list_invoices(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    quotation_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
) -> InvoiceListResponse:
    items, total = await repo.list_invoices(
        db, garage_id,
        customer_id=customer_id, status=status, quotation_id=quotation_id,
        page=page, page_size=page_size,
    )
    return InvoiceListResponse(
        items=[InvoiceOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
    )


async def update_invoice(
    db: AsyncSession,
    invoice_id: int,
    garage_id: int,
    *,
    request: InvoiceUpdateRequest,
    expected_version: int,
    user_id: int,
) -> InvoiceOut:
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise InvoiceStateError("Only draft invoices can be updated.")
    if inv.version != expected_version:
        raise InvoiceVersionError(f"Version mismatch: expected {expected_version}, got {inv.version}")

    if request.vehicle_id is not None:
        inv.vehicle_id = request.vehicle_id
    if request.repair_order_id is not None:
        inv.repair_order_id = request.repair_order_id
    if request.currency is not None:
        inv.currency = request.currency.upper()
    if request.due_at is not None:
        inv.due_at = request.due_at
    if request.notes is not None:
        inv.notes = request.notes

    inv.version += 1
    inv.updated_by = user_id
    await repo.save(db, inv)
    await db.commit()
    fresh = await repo.get_by_id(db, inv.id, garage_id)
    return InvoiceOut.model_validate(fresh)


async def delete_invoice(
    db: AsyncSession, invoice_id: int, garage_id: int, *, user_id: int
) -> None:
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise InvoiceStateError("Only draft invoices can be deleted.")
    await repo.soft_delete(db, inv, deleted_by=user_id)
    await db.commit()


# ---------------------------------------------------------------------------
# Line management
# ---------------------------------------------------------------------------

def _build_line(invoice: Invoice, req: InvoiceLineCreateRequest) -> InvoiceLine:
    lt = _line_total(req.unit_price_minor, req.quantity, req.discount_percent)
    return InvoiceLine(
        invoice_id=invoice.id or 0,
        kind=req.kind,
        part_id=req.part_id,
        description=req.description,
        quantity=req.quantity,
        unit_price_minor=req.unit_price_minor,
        discount_percent=req.discount_percent,
        vat_rate=req.vat_rate,
        line_total_minor=lt,
    )


async def add_line(
    db: AsyncSession,
    invoice_id: int,
    garage_id: int,
    *,
    request: InvoiceLineCreateRequest,
    expected_version: int,
    user_id: int,
) -> InvoiceOut:
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise InvoiceStateError("Lines can only be modified on draft invoices.")
    if inv.version != expected_version:
        raise InvoiceVersionError(f"Version mismatch: expected {expected_version}, got {inv.version}")

    line = InvoiceLine(
        invoice_id=inv.id,
        kind=request.kind,
        part_id=request.part_id,
        description=request.description,
        quantity=request.quantity,
        unit_price_minor=request.unit_price_minor,
        discount_percent=request.discount_percent,
        vat_rate=request.vat_rate,
        line_total_minor=0,
    )
    await repo.add_line(db, line)
    inv.lines.append(line)
    _recalculate_totals(inv)
    inv.version += 1
    inv.updated_by = user_id
    await repo.save(db, inv)
    await db.commit()
    fresh = await repo.get_by_id(db, inv.id, garage_id)
    return InvoiceOut.model_validate(fresh)


async def update_line(
    db: AsyncSession,
    invoice_id: int,
    line_id: int,
    garage_id: int,
    *,
    request: InvoiceLineUpdateRequest,
    expected_version: int,
    user_id: int,
) -> InvoiceOut:
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise InvoiceStateError("Lines can only be modified on draft invoices.")
    if inv.version != expected_version:
        raise InvoiceVersionError(f"Version mismatch: expected {expected_version}, got {inv.version}")

    line = await repo.get_line(db, line_id, invoice_id)
    if not line:
        raise InvoiceLineNotFoundError(line_id)

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

    _recalculate_totals(inv)
    inv.version += 1
    inv.updated_by = user_id
    await repo.save(db, inv)
    await db.commit()
    fresh = await repo.get_by_id(db, inv.id, garage_id)
    return InvoiceOut.model_validate(fresh)


async def remove_line(
    db: AsyncSession,
    invoice_id: int,
    line_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> InvoiceOut:
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise InvoiceStateError("Lines can only be modified on draft invoices.")
    if inv.version != expected_version:
        raise InvoiceVersionError(f"Version mismatch: expected {expected_version}, got {inv.version}")

    line = await repo.get_line(db, line_id, invoice_id)
    if not line:
        raise InvoiceLineNotFoundError(line_id)

    inv.lines = [l for l in inv.lines if l.id != line_id]
    await repo.delete_line(db, line)
    _recalculate_totals(inv)
    inv.version += 1
    inv.updated_by = user_id
    await repo.save(db, inv)
    await db.commit()
    fresh = await repo.get_by_id(db, inv.id, garage_id)
    return InvoiceOut.model_validate(fresh)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

async def issue_invoice(
    db: AsyncSession,
    invoice_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> InvoiceOut:
    """DRAFT → ISSUED.  Assigns doc_number from sequence and locks the invoice."""
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise InvoiceStateError(f"Cannot issue an invoice in status '{inv.status.value}'.")
    if inv.version != expected_version:
        raise InvoiceVersionError(f"Version mismatch: expected {expected_version}, got {inv.version}")

    # Credit limit check before issuing (raises CreditLimitExceededError in block mode)
    from app.modules.customer.credit_service import check_credit_limit, post_balance_event
    from app.core.config import get_settings
    await check_credit_limit(
        db, customer_id=inv.customer_id, garage_id=garage_id,
        additional_amount_minor=inv.total_minor,
    )

    seq = await seq_service.next(db, garage_id=garage_id, doc_type="INV")
    inv.doc_number = seq.formatted
    inv.status = InvoiceStatus.issued
    inv.issued_at = datetime.now(tz=timezone.utc)
    inv.version += 1
    inv.updated_by = user_id
    await repo.save(db, inv)

    # Post debit to customer balance ledger (+total = customer owes more)
    await post_balance_event(
        db,
        customer_id=inv.customer_id,
        garage_id=garage_id,
        reason="invoice_issued",
        delta_minor=inv.total_minor,
        currency=get_settings().credit_currency,
        ref_type="invoice",
        ref_id=inv.id,
        created_by=user_id,
    )

    # Auto-deduct any unapplied advance payments for this customer
    from app.modules.advance_payment.service import apply_advances_to_invoice
    await apply_advances_to_invoice(
        db,
        invoice_id=inv.id,
        customer_id=inv.customer_id,
        garage_id=garage_id,
    )

    await db.commit()
    fresh = await repo.get_by_id(db, inv.id, garage_id)
    logger.info("invoice_issued", invoice_id=invoice_id, doc_number=fresh.doc_number if fresh else None)
    return InvoiceOut.model_validate(fresh)


async def cancel_invoice(
    db: AsyncSession,
    invoice_id: int,
    garage_id: int,
    *,
    expected_version: int,
    user_id: int,
) -> InvoiceOut:
    """DRAFT/ISSUED → CANCELLED."""
    inv = await repo.get_by_id(db, invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(invoice_id)
    if inv.status not in (
        InvoiceStatus.draft, InvoiceStatus.issued,
        InvoiceStatus.partial, InvoiceStatus.paid,
    ):
        raise InvoiceStateError(f"Cannot cancel an invoice in status '{inv.status.value}'.")
    if inv.version != expected_version:
        raise InvoiceVersionError(f"Version mismatch: expected {expected_version}, got {inv.version}")

    was_issued = inv.status in (
        InvoiceStatus.issued, InvoiceStatus.partial, InvoiceStatus.paid
    )
    paid_amount = inv.paid_amount_minor or 0

    inv.status = InvoiceStatus.cancelled
    inv.version += 1
    inv.updated_by = user_id
    await repo.save(db, inv)

    # Reverse the balance debit only if the invoice had been issued
    if was_issued:
        from app.modules.customer.credit_service import post_balance_event
        from app.core.config import get_settings
        await post_balance_event(
            db,
            customer_id=inv.customer_id,
            garage_id=garage_id,
            reason="invoice_cancelled",
            delta_minor=-inv.total_minor,
            currency=get_settings().credit_currency,
            ref_type="invoice",
            ref_id=inv.id,
            created_by=user_id,
        )

        # Auto-issue a credit note for any amount already paid
        if paid_amount > 0:
            from app.modules.credit_note.service import _auto_create_and_issue_credit_note
            await _auto_create_and_issue_credit_note(
                db,
                invoice_id=inv.id,
                garage_id=garage_id,
                total_minor=paid_amount,
                reason="Auto-generated: invoice cancelled after payment.",
                user_id=user_id,
            )

    await db.commit()
    fresh = await repo.get_by_id(db, inv.id, garage_id)
    logger.info("invoice_cancelled", invoice_id=invoice_id)
    return InvoiceOut.model_validate(fresh)


# ---------------------------------------------------------------------------
# Quotation → Invoice conversion
# ---------------------------------------------------------------------------

async def convert_quotation(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    due_at: Optional[datetime] = None,
    user_id: int,
) -> InvoiceOut:
    """Convert an approved (or sent) quotation into a draft invoice.

    - Copies all lines verbatim.
    - Sets quotation.status = 'converted'.
    - Returns the new draft invoice.
    """
    # Import here to avoid circular imports at module level
    from app.modules.quotation import repository as quot_repo
    from app.modules.quotation.models import QuotationStatus

    quotation = await quot_repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        from app.modules.quotation.service import QuotationNotFoundError
        raise QuotationNotFoundError(quotation_id)

    if quotation.status == QuotationStatus.converted:
        raise QuotationAlreadyConvertedError(f"Quotation {quotation_id} has already been converted.")

    if quotation.status not in (QuotationStatus.approved, QuotationStatus.sent):
        raise InvoiceStateError(
            f"Only sent or approved quotations can be converted. Current status: '{quotation.status.value}'."
        )

    # Check not already converted (belt-and-suspenders for concurrent requests)
    existing, total = await repo.list_invoices(db, garage_id, quotation_id=quotation_id)
    if total > 0:
        raise QuotationAlreadyConvertedError(f"Quotation {quotation_id} has already been converted.")

    invoice = Invoice(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        customer_id=quotation.customer_id,
        vehicle_id=quotation.vehicle_id,
        repair_order_id=quotation.repair_order_id,
        quotation_id=quotation.id,
        currency=quotation.currency,
        due_at=due_at,
        notes=quotation.notes,
        status=InvoiceStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )

    # Copy lines
    for ql in quotation.lines:
        invoice.lines.append(InvoiceLine(
            invoice_id=0,
            kind=InvoiceLineKind(ql.kind.value) if hasattr(ql.kind, "value") else InvoiceLineKind.service,
            part_id=ql.part_id,
            description=ql.description,
            quantity=ql.quantity,
            unit_price_minor=ql.unit_price_minor,
            discount_percent=ql.discount_percent,
            vat_rate=ql.vat_rate,
            line_total_minor=ql.line_total_minor,
        ))

    _recalculate_totals(invoice)
    await repo.create(db, invoice)

    # Mark quotation as converted
    quotation.status = QuotationStatus.converted
    quotation.version += 1
    quotation.updated_by = user_id
    await db.flush()
    await db.commit()

    fresh = await repo.get_by_id(db, invoice.id, garage_id)
    logger.info(
        "quotation_converted",
        quotation_id=quotation_id,
        invoice_id=invoice.id,
        garage_id=garage_id,
    )
    return InvoiceOut.model_validate(fresh)
