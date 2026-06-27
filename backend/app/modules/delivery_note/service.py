"""Delivery Note service — business logic and lifecycle transitions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.delivery_note import repository as repo
from app.modules.delivery_note.models import (
    DeliveryNote,
    DeliveryNoteLine,
    DeliveryNoteLineKind,
    DeliveryNoteStatus,
)
from app.modules.delivery_note.schemas import (
    DeliveryNoteCreateRequest,
    DeliveryNoteLineCreateRequest,
    DeliveryNoteLineUpdateRequest,
    DeliveryNoteListResponse,
    DeliveryNoteOut,
    DeliveryNoteUpdateRequest,
)
from app.modules.parts.stock_models import StockMovementType
from app.modules.parts.stock_service import NegativeStockError, record_movement
from app.modules.sequence import service as seq_service

logger = get_logger("delivery_note.service")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DeliveryNoteNotFoundError(Exception):
    pass


class DeliveryNoteLineNotFoundError(Exception):
    pass


class DeliveryNoteStateError(Exception):
    """Raised when a status transition or edit is illegal."""
    pass


class DeliveryNoteVersionError(Exception):
    """Raised on optimistic concurrency mismatch."""
    pass


# ---------------------------------------------------------------------------
# Money helpers
# ---------------------------------------------------------------------------

def _line_total(unit_price_minor: int, quantity: Decimal) -> int:
    total = Decimal(unit_price_minor) * quantity
    return int(total.to_integral_value(rounding=ROUND_HALF_UP))


def _line_vat(line_total: int, vat_rate: Decimal) -> int:
    vat = Decimal(line_total) * vat_rate / Decimal("100")
    return int(vat.to_integral_value(rounding=ROUND_HALF_UP))


def _recalculate_totals(dn: DeliveryNote) -> None:
    subtotal = 0
    vat_total = 0
    for line in dn.lines:
        lt = _line_total(line.unit_price_minor, line.quantity)
        lv = _line_vat(lt, line.vat_rate)
        line.line_total_minor = lt
        subtotal += lt
        vat_total += lv
    dn.subtotal_minor = subtotal
    dn.vat_minor = vat_total
    dn.total_minor = subtotal + vat_total


def _build_line(dn: DeliveryNote, req: DeliveryNoteLineCreateRequest) -> DeliveryNoteLine:
    lt = _line_total(req.unit_price_minor, req.quantity)
    return DeliveryNoteLine(
        delivery_note_id=dn.id or 0,
        kind=req.kind,
        part_id=req.part_id,
        description=req.description,
        quantity=req.quantity,
        unit_price_minor=req.unit_price_minor,
        vat_rate=req.vat_rate,
        line_total_minor=lt,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_delivery_note(
    db: AsyncSession,
    *,
    request: DeliveryNoteCreateRequest,
    garage_id: int,
    user_id: int,
) -> DeliveryNoteOut:
    logger.info("create_delivery_note_start", garage_id=garage_id, customer_id=request.customer_id)
    dn = DeliveryNote(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        customer_id=request.customer_id,
        vehicle_id=request.vehicle_id,
        currency=request.currency.upper(),
        notes=request.notes,
        status=DeliveryNoteStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )
    for line_req in request.lines:
        dn.lines.append(_build_line(dn, line_req))

    _recalculate_totals(dn)
    await repo.create(db, dn)
    await db.commit()

    fresh = await repo.get_by_id(db, dn.id, garage_id)
    logger.info("delivery_note_created", dn_id=dn.id, garage_id=garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def from_quotation(
    db: AsyncSession,
    quotation_id: int,
    garage_id: int,
    *,
    user_id: int,
) -> DeliveryNoteOut:
    """Create a draft delivery note from an approved/sent quotation, copying all lines."""
    from app.modules.quotation import repository as quot_repo

    quotation = await quot_repo.get_by_id(db, quotation_id, garage_id)
    if not quotation:
        raise DeliveryNoteNotFoundError(f"Quotation {quotation_id} not found")

    # Map quotation line kinds to delivery note line kinds
    KIND_MAP = {"labor": "service", "part": "part", "service": "service", "other": "other"}

    dn = DeliveryNote(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        customer_id=quotation.customer_id,
        vehicle_id=quotation.vehicle_id,
        currency=quotation.currency,
        notes=quotation.notes,
        status=DeliveryNoteStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )
    for ql in quotation.lines:
        kind_str = KIND_MAP.get(ql.kind.value if hasattr(ql.kind, "value") else str(ql.kind), "other")
        lt = _line_total(ql.unit_price_minor, ql.quantity)
        dn.lines.append(DeliveryNoteLine(
            delivery_note_id=0,
            kind=DeliveryNoteLineKind(kind_str),
            part_id=ql.part_id,
            description=ql.description,
            quantity=ql.quantity,
            unit_price_minor=ql.unit_price_minor,
            vat_rate=ql.vat_rate,
            line_total_minor=lt,
        ))

    _recalculate_totals(dn)
    await repo.create(db, dn)
    await db.commit()

    fresh = await repo.get_by_id(db, dn.id, garage_id)
    logger.info("delivery_note_from_quotation", dn_id=dn.id, quotation_id=quotation_id, garage_id=garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def get_delivery_note(
    db: AsyncSession, public_id: str, garage_id: int
) -> DeliveryNoteOut:
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    out = DeliveryNoteOut.model_validate(dn)
    if dn.invoice_id:
        from sqlalchemy import select as sa_select
        from app.modules.invoice.models import Invoice
        row = await db.execute(sa_select(Invoice.public_id).where(Invoice.id == dn.invoice_id))
        inv_pub = row.scalar_one_or_none()
        if inv_pub:
            out.invoice_public_id = str(inv_pub)
    return out


async def list_delivery_notes(
    db: AsyncSession,
    garage_id: int,
    *,
    customer_id: Optional[int] = None,
    status: Optional[DeliveryNoteStatus] = None,
    available_for_invoice: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> DeliveryNoteListResponse:
    from sqlalchemy import select as sa_select
    from app.modules.customer.models import Customer

    items, total = await repo.list_delivery_notes(
        db, garage_id, customer_id=customer_id, status=status,
        available_for_invoice=available_for_invoice, page=page, page_size=page_size
    )
    cust_ids = list({d.customer_id for d in items})
    customers_map: dict[int, str] = {}
    if cust_ids:
        res = await db.execute(sa_select(Customer).where(Customer.id.in_(cust_ids)))
        customers_map = {c.id: c.full_name for c in res.scalars()}

    out_items = []
    for d in items:
        out = DeliveryNoteOut.model_validate(d)
        out.customer_name = customers_map.get(d.customer_id)
        out_items.append(out)

    return DeliveryNoteListResponse(items=out_items, total=total, page=page, page_size=page_size)


async def update_delivery_note(
    db: AsyncSession,
    public_id: str,
    garage_id: int,
    *,
    request: DeliveryNoteUpdateRequest,
    expected_version: int,
    user_id: int,
) -> DeliveryNoteOut:
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status != DeliveryNoteStatus.draft:
        raise DeliveryNoteStateError("Only draft delivery notes can be updated.")
    if dn.version != expected_version:
        raise DeliveryNoteVersionError(f"Version mismatch: expected {expected_version}, got {dn.version}")

    if request.vehicle_id is not None:
        dn.vehicle_id = request.vehicle_id
    if request.currency is not None:
        dn.currency = request.currency.upper()
    if request.notes is not None:
        dn.notes = request.notes

    dn.version += 1
    dn.updated_by = user_id
    await repo.save(db, dn)
    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def delete_delivery_note(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> None:
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status not in (DeliveryNoteStatus.draft, DeliveryNoteStatus.cancelled):
        raise DeliveryNoteStateError("Only draft or cancelled delivery notes can be deleted.")
    await repo.soft_delete(db, dn, deleted_by=user_id)
    await db.commit()


# ---------------------------------------------------------------------------
# Line management
# ---------------------------------------------------------------------------

async def add_line(
    db: AsyncSession,
    public_id: str,
    garage_id: int,
    *,
    request: DeliveryNoteLineCreateRequest,
    user_id: int,
) -> DeliveryNoteOut:
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status != DeliveryNoteStatus.draft:
        raise DeliveryNoteStateError("Lines can only be added to draft delivery notes.")

    line = _build_line(dn, request)
    dn.lines.append(line)
    _recalculate_totals(dn)
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def update_line(
    db: AsyncSession,
    public_id: str,
    line_id: int,
    garage_id: int,
    *,
    request: DeliveryNoteLineUpdateRequest,
    user_id: int,
) -> DeliveryNoteOut:
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status != DeliveryNoteStatus.draft:
        raise DeliveryNoteStateError("Lines can only be updated on draft delivery notes.")

    line = await repo.get_line(db, line_id, dn.id)
    if not line:
        raise DeliveryNoteLineNotFoundError(line_id)

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
    if request.vat_rate is not None:
        line.vat_rate = request.vat_rate

    _recalculate_totals(dn)
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def remove_line(
    db: AsyncSession,
    public_id: str,
    line_id: int,
    garage_id: int,
    *,
    user_id: int,
) -> DeliveryNoteOut:
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status != DeliveryNoteStatus.draft:
        raise DeliveryNoteStateError("Lines can only be removed from draft delivery notes.")

    line = await repo.get_line(db, line_id, dn.id)
    if not line:
        raise DeliveryNoteLineNotFoundError(line_id)

    await repo.delete_line(db, line)
    # Refresh lines before recalculating
    await db.refresh(dn)
    _recalculate_totals(dn)
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    return DeliveryNoteOut.model_validate(fresh)


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

async def issue_delivery_note(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> DeliveryNoteOut:
    """Assign a document number, lock the delivery note, and deduct stock."""
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status != DeliveryNoteStatus.draft:
        raise DeliveryNoteStateError("Only draft delivery notes can be issued.")

    # Credit limit check (raises CreditLimitExceededError in block mode).
    # Returns True when an admin override was consumed — we record this on the BL so
    # the resulting invoice can skip its own credit check (same transaction, already approved).
    issued_under_override = False
    if dn.customer_id is not None:
        from app.modules.customer.credit_service import check_credit_limit, CreditLimitExceededError
        issued_under_override = await check_credit_limit(
            db,
            customer_id=dn.customer_id,
            garage_id=garage_id,
            additional_amount_minor=dn.total_minor,
            doc_type="delivery_note",
            source_document_public_id=dn.public_id,
        )

    seq = await seq_service.next(db, garage_id=garage_id, doc_type="BL")
    dn.doc_number = seq.formatted
    dn.status = DeliveryNoteStatus.issued
    dn.issued_at = datetime.now(tz=timezone.utc)
    dn.issued_under_override = issued_under_override
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()

    # Deduct stock for every catalogued part line
    for line in dn.lines:
        if line.part_id is None:
            continue
        if line.kind not in (DeliveryNoteLineKind.part, DeliveryNoteLineKind.accessory):
            continue
        qty = int(line.quantity)
        if qty <= 0:
            continue
        try:
            await record_movement(
                db,
                garage_id=garage_id,
                part_id=line.part_id,
                movement_type=StockMovementType.out,
                quantity=qty,
                ref_type="delivery_note",
                ref_id=dn.public_id,
                reason=f"BL émis : {dn.doc_number}",
                created_by_user_id=user_id,
                allow_negative=False,
            )
        except NegativeStockError as e:
            await db.rollback()
            raise DeliveryNoteStateError(
                f"Stock insuffisant pour « {line.description} » : "
                f"disponible {e.available}, demandé {e.requested}"
            )

    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    logger.info("delivery_note_issued", dn_id=dn.id, doc_number=dn.doc_number, garage_id=garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def mark_delivered(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> DeliveryNoteOut:
    """Mark the delivery note as delivered (goods handed to customer)."""
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status != DeliveryNoteStatus.issued:
        raise DeliveryNoteStateError("Only issued delivery notes can be marked as delivered.")

    dn.status = DeliveryNoteStatus.delivered
    dn.delivered_at = datetime.now(tz=timezone.utc)
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    logger.info("delivery_note_delivered", dn_id=dn.id, garage_id=garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def cancel_delivery_note(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> DeliveryNoteOut:
    """Cancel a draft or issued delivery note, reversing stock if already issued."""
    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status not in (DeliveryNoteStatus.draft, DeliveryNoteStatus.issued):
        raise DeliveryNoteStateError("Only draft or issued delivery notes can be cancelled.")

    was_issued = dn.status == DeliveryNoteStatus.issued

    dn.status = DeliveryNoteStatus.cancelled
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()

    # Restore stock for every part line whose stock was deducted at issue time
    if was_issued:
        for line in dn.lines:
            if line.part_id is None:
                continue
            if line.kind not in (DeliveryNoteLineKind.part, DeliveryNoteLineKind.accessory):
                continue
            qty = int(line.quantity)
            if qty <= 0:
                continue
            await record_movement(
                db,
                garage_id=garage_id,
                part_id=line.part_id,
                movement_type=StockMovementType.in_,
                quantity=qty,
                ref_type="delivery_note",
                ref_id=dn.public_id,
                reason=f"BL annulé : {dn.doc_number}",
                created_by_user_id=user_id,
            )

    await db.commit()
    fresh = await repo.get_by_id(db, dn.id, garage_id)
    logger.info("delivery_note_cancelled", dn_id=dn.id, was_issued=was_issued, garage_id=garage_id)
    return DeliveryNoteOut.model_validate(fresh)


async def convert_to_invoice(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> DeliveryNoteOut:
    """Convert an issued or delivered BL into a draft Invoice."""
    from app.modules.invoice.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceLineKind

    dn = await repo.get_by_public_id(db, public_id, garage_id)
    if not dn:
        raise DeliveryNoteNotFoundError(public_id)
    if dn.status not in (DeliveryNoteStatus.issued, DeliveryNoteStatus.delivered):
        raise DeliveryNoteStateError("Only issued or delivered delivery notes can be converted to invoices.")
    if dn.invoice_id is not None:
        raise DeliveryNoteStateError("This delivery note has already been converted to an invoice.")

    invoice = Invoice(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        customer_id=dn.customer_id,
        vehicle_id=dn.vehicle_id,
        currency=dn.currency,
        notes=f"Converti depuis BL {dn.doc_number or dn.public_id}",
        status=InvoiceStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )

    # Map BL line kinds to InvoiceLineKind
    _kind_map = {
        DeliveryNoteLineKind.part: InvoiceLineKind.part,
        DeliveryNoteLineKind.accessory: InvoiceLineKind.part,
        DeliveryNoteLineKind.service: InvoiceLineKind.service,
        DeliveryNoteLineKind.other: InvoiceLineKind.other,
    }

    for bl_line in dn.lines:
        inv_line = InvoiceLine(
            kind=_kind_map.get(bl_line.kind, InvoiceLineKind.other),
            part_id=bl_line.part_id,
            description=bl_line.description,
            quantity=bl_line.quantity,
            unit_price_minor=bl_line.unit_price_minor,
            discount_percent=Decimal("0"),
            vat_rate=bl_line.vat_rate,
            line_total_minor=bl_line.line_total_minor,
        )
        invoice.lines.append(inv_line)

    # Compute invoice totals
    invoice.subtotal_minor = dn.subtotal_minor
    invoice.vat_minor = dn.vat_minor
    invoice.total_minor = dn.total_minor
    invoice.outstanding_minor = dn.total_minor

    db.add(invoice)
    await db.flush()

    dn.invoice_id = invoice.id
    dn.version += 1
    dn.updated_by = user_id
    await db.flush()
    await db.commit()

    fresh = await repo.get_by_id(db, dn.id, garage_id)
    logger.info("delivery_note_converted", dn_id=dn.id, invoice_id=invoice.id, garage_id=garage_id)
    result = DeliveryNoteOut.model_validate(fresh)
    result.invoice_public_id = str(invoice.public_id)
    return result
