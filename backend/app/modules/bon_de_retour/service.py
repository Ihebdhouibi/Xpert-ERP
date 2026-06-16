"""Bon de Retour service — business logic and lifecycle transitions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.bon_de_retour import repository as repo
from app.modules.bon_de_retour.models import (
    BonDeRetour,
    BonDeRetourLine,
    BonDeRetourPartyType,
    BonDeRetourStatus,
    SupplierCreditNote,
    SupplierCreditNoteStatus,
)
from app.modules.bon_de_retour.schemas import (
    BonDeRetourCreateRequest,
    BonDeRetourLineCreateRequest,
    BonDeRetourLineUpdateRequest,
    BonDeRetourListResponse,
    BonDeRetourOut,
    BonDeRetourUpdateRequest,
    CreateCreditNoteRequest,
    CreateSupplierCreditNoteRequest,
    SupplierCreditNoteListResponse,
    SupplierCreditNoteOut,
)
from app.modules.sequence import service as seq_service

logger = get_logger("bon_de_retour.service")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class BonDeRetourNotFoundError(Exception):
    pass


class BonDeRetourLineNotFoundError(Exception):
    pass


class BonDeRetourStateError(Exception):
    """Raised when a status transition or edit is illegal."""
    pass


class BonDeRetourVersionError(Exception):
    """Raised on optimistic concurrency mismatch."""
    pass


class SupplierCreditNoteNotFoundError(Exception):
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


def _recalculate_totals(bdr: BonDeRetour) -> None:
    subtotal = 0
    vat_total = 0
    for line in bdr.lines:
        lt = _line_total(line.unit_price_minor, line.quantity)
        lv = _line_vat(lt, line.vat_rate)
        line.line_total_minor = lt
        subtotal += lt
        vat_total += lv
    bdr.subtotal_minor = subtotal
    bdr.vat_minor = vat_total
    bdr.total_minor = subtotal + vat_total


def _build_line(req: BonDeRetourLineCreateRequest) -> BonDeRetourLine:
    return BonDeRetourLine(
        bon_de_retour_id=0,
        part_id=req.part_id,
        description=req.description,
        quantity=req.quantity,
        unit_price_minor=req.unit_price_minor,
        vat_rate=req.vat_rate,
        line_total_minor=_line_total(req.unit_price_minor, req.quantity),
        condition=req.condition,
        restock=req.restock,
    )


async def _scalar(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalar_one_or_none()


async def _build_out(db: AsyncSession, bdr: BonDeRetour) -> BonDeRetourOut:
    """Validate ORM → schema and populate denormalised display fields."""
    from app.modules.customer.models import Customer
    from app.modules.supplier.models import Supplier
    from app.modules.credit_note.models import CreditNote

    out = BonDeRetourOut.model_validate(bdr)
    if bdr.customer_id:
        out.customer_name = await _scalar(db, select(Customer.full_name).where(Customer.id == bdr.customer_id))
    if bdr.supplier_id:
        out.supplier_name = await _scalar(db, select(Supplier.name).where(Supplier.id == bdr.supplier_id))
    if bdr.credit_note_id:
        out.credit_note_doc_number = await _scalar(
            db, select(CreditNote.doc_number).where(CreditNote.id == bdr.credit_note_id)
        )
    if bdr.supplier_credit_note_id:
        out.supplier_credit_note_doc_number = await _scalar(
            db, select(SupplierCreditNote.doc_number).where(SupplierCreditNote.id == bdr.supplier_credit_note_id)
        )
    return out


async def _ensure_party_exists(db: AsyncSession, *, party_type: BonDeRetourPartyType, customer_id, supplier_id, garage_id: int) -> None:
    if party_type == BonDeRetourPartyType.client:
        from app.modules.customer.models import Customer
        found = await _scalar(db, select(Customer.id).where(Customer.id == customer_id, Customer.garage_id == garage_id))
        if found is None:
            raise BonDeRetourStateError(f"Customer {customer_id} not found.")
    else:
        from app.modules.supplier.models import Supplier
        found = await _scalar(db, select(Supplier.id).where(Supplier.id == supplier_id, Supplier.garage_id == garage_id))
        if found is None:
            raise BonDeRetourStateError(f"Supplier {supplier_id} not found.")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_bon_de_retour(
    db: AsyncSession,
    *,
    request: BonDeRetourCreateRequest,
    garage_id: int,
    user_id: int,
) -> BonDeRetourOut:
    logger.info("create_bon_de_retour_start", garage_id=garage_id, party_type=getattr(request.party_type, "value", request.party_type))
    await _ensure_party_exists(
        db, party_type=request.party_type, customer_id=request.customer_id,
        supplier_id=request.supplier_id, garage_id=garage_id,
    )
    bdr = BonDeRetour(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        party_type=request.party_type,
        customer_id=request.customer_id,
        supplier_id=request.supplier_id,
        source_invoice_id=request.source_invoice_id,
        source_supplier_invoice_id=request.source_supplier_invoice_id,
        currency=request.currency.upper(),
        reason=request.reason,
        notes=request.notes,
        status=BonDeRetourStatus.draft,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )
    for line_req in request.lines:
        bdr.lines.append(_build_line(line_req))

    _recalculate_totals(bdr)
    await repo.create(db, bdr)
    await db.commit()

    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    logger.info("bon_de_retour_created", bdr_id=bdr.id, garage_id=garage_id)
    return await _build_out(db, fresh)


async def get_bon_de_retour(db: AsyncSession, public_id: str, garage_id: int) -> BonDeRetourOut:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    return await _build_out(db, bdr)


async def list_bon_de_retour(
    db: AsyncSession,
    garage_id: int,
    *,
    party_type: Optional[BonDeRetourPartyType] = None,
    status: Optional[BonDeRetourStatus] = None,
    page: int = 1,
    page_size: int = 25,
) -> BonDeRetourListResponse:
    items, total = await repo.list_bon_de_retour(
        db, garage_id, party_type=party_type, status=status, page=page, page_size=page_size
    )
    return BonDeRetourListResponse(
        items=[await _build_out(db, i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_bon_de_retour(
    db: AsyncSession,
    public_id: str,
    garage_id: int,
    *,
    request: BonDeRetourUpdateRequest,
    expected_version: int,
    user_id: int,
) -> BonDeRetourOut:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status != BonDeRetourStatus.draft:
        raise BonDeRetourStateError("Only draft bon de retour can be updated.")
    if bdr.version != expected_version:
        raise BonDeRetourVersionError(f"Version mismatch: expected {expected_version}, got {bdr.version}")

    if request.source_invoice_id is not None:
        bdr.source_invoice_id = request.source_invoice_id
    if request.source_supplier_invoice_id is not None:
        bdr.source_supplier_invoice_id = request.source_supplier_invoice_id
    if request.currency is not None:
        bdr.currency = request.currency.upper()
    if request.reason is not None:
        bdr.reason = request.reason
    if request.notes is not None:
        bdr.notes = request.notes

    bdr.version += 1
    bdr.updated_by = user_id
    await repo.save(db, bdr)
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    return await _build_out(db, fresh)


async def delete_bon_de_retour(db: AsyncSession, public_id: str, garage_id: int, *, user_id: int) -> None:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status not in (BonDeRetourStatus.draft, BonDeRetourStatus.cancelled):
        raise BonDeRetourStateError("Only draft or cancelled bon de retour can be deleted.")
    await repo.soft_delete(db, bdr, deleted_by=user_id)
    await db.commit()


# ---------------------------------------------------------------------------
# Line management
# ---------------------------------------------------------------------------

async def add_line(
    db: AsyncSession, public_id: str, garage_id: int, *, request: BonDeRetourLineCreateRequest, user_id: int
) -> BonDeRetourOut:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status != BonDeRetourStatus.draft:
        raise BonDeRetourStateError("Lines can only be added to draft bon de retour.")

    bdr.lines.append(_build_line(request))
    _recalculate_totals(bdr)
    bdr.version += 1
    bdr.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    return await _build_out(db, fresh)


async def update_line(
    db: AsyncSession, public_id: str, line_id: int, garage_id: int, *, request: BonDeRetourLineUpdateRequest, user_id: int
) -> BonDeRetourOut:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status != BonDeRetourStatus.draft:
        raise BonDeRetourStateError("Lines can only be updated on draft bon de retour.")

    line = await repo.get_line(db, line_id, bdr.id)
    if not line:
        raise BonDeRetourLineNotFoundError(line_id)

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
    if request.condition is not None:
        line.condition = request.condition
    if request.restock is not None:
        line.restock = request.restock

    _recalculate_totals(bdr)
    bdr.version += 1
    bdr.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    return await _build_out(db, fresh)


async def remove_line(
    db: AsyncSession, public_id: str, line_id: int, garage_id: int, *, user_id: int
) -> BonDeRetourOut:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status != BonDeRetourStatus.draft:
        raise BonDeRetourStateError("Lines can only be removed from draft bon de retour.")

    line = await repo.get_line(db, line_id, bdr.id)
    if not line:
        raise BonDeRetourLineNotFoundError(line_id)

    await repo.delete_line(db, line)
    await db.refresh(bdr)
    _recalculate_totals(bdr)
    bdr.version += 1
    bdr.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    return await _build_out(db, fresh)


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

async def confirm_bon_de_retour(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> BonDeRetourOut:
    """DRAFT → CONFIRMED. Assigns BR number and applies the stock movement.

    * client returns  → stock IN  (réintégration) for part lines with restock=True
    * supplier returns → stock OUT (goods leave our stock) for part lines

    The stock movement and the status change commit atomically; a NegativeStockError
    on a supplier return rolls the whole transaction back.
    """
    from app.modules.parts.stock_models import StockMovementType
    from app.modules.parts.stock_service import record_movement

    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status != BonDeRetourStatus.draft:
        raise BonDeRetourStateError("Only draft bon de retour can be confirmed.")
    if not bdr.lines:
        raise BonDeRetourStateError("Cannot confirm an empty bon de retour.")

    seq = await seq_service.next(db, garage_id=garage_id, doc_type="BR")
    bdr.doc_number = seq.formatted
    bdr.status = BonDeRetourStatus.confirmed
    bdr.confirmed_at = datetime.now(tz=timezone.utc)
    bdr.version += 1
    bdr.updated_by = user_id

    is_client = bdr.party_type == BonDeRetourPartyType.client
    for line in bdr.lines:
        if line.part_id is None:
            continue
        qty = int(Decimal(line.quantity).to_integral_value(rounding=ROUND_HALF_UP))
        if qty <= 0:
            continue
        if is_client:
            if not line.restock:
                continue
            await record_movement(
                db, garage_id=garage_id, part_id=line.part_id,
                movement_type=StockMovementType.in_, quantity=qty, unit_cost_minor=None,
                ref_type="bon_de_retour", ref_id=bdr.public_id,
                reason=f"Retour client {bdr.doc_number}", created_by_user_id=user_id,
            )
        else:
            await record_movement(
                db, garage_id=garage_id, part_id=line.part_id,
                movement_type=StockMovementType.out, quantity=qty, unit_cost_minor=None,
                ref_type="bon_de_retour", ref_id=bdr.public_id,
                reason=f"Retour fournisseur {bdr.doc_number}", created_by_user_id=user_id,
            )

    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    logger.info("bon_de_retour_confirmed", bdr_id=bdr.id, doc_number=bdr.doc_number, party_type=getattr(bdr.party_type, "value", bdr.party_type))
    return await _build_out(db, fresh)


async def cancel_bon_de_retour(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> BonDeRetourOut:
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.status != BonDeRetourStatus.draft:
        raise BonDeRetourStateError("Only draft bon de retour can be cancelled.")

    bdr.status = BonDeRetourStatus.cancelled
    bdr.cancelled_at = datetime.now(tz=timezone.utc)
    bdr.version += 1
    bdr.updated_by = user_id
    await repo.save(db, bdr)
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    logger.info("bon_de_retour_cancelled", bdr_id=bdr.id)
    return await _build_out(db, fresh)


async def reverse_bon_de_retour(
    db: AsyncSession, public_id: str, garage_id: int, *, user_id: int
) -> BonDeRetourOut:
    """CONFIRMED → REVERSED. Reverses every stock movement that was applied on confirm.

    * client return reversal → stock OUT for each restocked part line (undoes the IN)
    * supplier return reversal → stock IN for each part line (undoes the OUT)

    The reversal uses ``ref_type="bon_de_retour_reversal"`` so the movement log
    is traceable.  A NegativeStockError on a client-return reversal (stock was
    already consumed) rolls the whole transaction back.
    """
    from app.modules.parts.stock_models import StockMovementType
    from app.modules.parts.stock_service import record_movement

    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    status_val = getattr(bdr.status, "value", bdr.status)
    if status_val != "confirmed":
        raise BonDeRetourStateError("Only confirmed bon de retour can be reversed.")

    is_client = getattr(bdr.party_type, "value", bdr.party_type) == "client"
    for line in bdr.lines:
        if line.part_id is None:
            continue
        qty = int(Decimal(line.quantity).to_integral_value(rounding=ROUND_HALF_UP))
        if qty <= 0:
            continue
        if is_client:
            if not line.restock:
                continue
            await record_movement(
                db, garage_id=garage_id, part_id=line.part_id,
                movement_type=StockMovementType.out, quantity=qty, unit_cost_minor=None,
                ref_type="bon_de_retour_reversal", ref_id=bdr.public_id,
                reason=f"Contre-passation {bdr.doc_number}", created_by_user_id=user_id,
            )
        else:
            await record_movement(
                db, garage_id=garage_id, part_id=line.part_id,
                movement_type=StockMovementType.in_, quantity=qty, unit_cost_minor=None,
                ref_type="bon_de_retour_reversal", ref_id=bdr.public_id,
                reason=f"Contre-passation {bdr.doc_number}", created_by_user_id=user_id,
            )

    bdr.status = BonDeRetourStatus.reversed
    bdr.reversed_at = datetime.now(tz=timezone.utc)
    bdr.version += 1
    bdr.updated_by = user_id
    await db.flush()
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    logger.info(
        "bon_de_retour_reversed",
        bdr_id=bdr.id,
        doc_number=bdr.doc_number,
        party_type=getattr(bdr.party_type, "value", bdr.party_type),
    )
    return await _build_out(db, fresh)


# ---------------------------------------------------------------------------
# Avoir creation
# ---------------------------------------------------------------------------

async def create_credit_note_for_br(
    db: AsyncSession, public_id: str, garage_id: int, *, request: CreateCreditNoteRequest, user_id: int
) -> BonDeRetourOut:
    """Client side — create + issue an avoir via the existing credit_note module."""
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.party_type != BonDeRetourPartyType.client:
        raise BonDeRetourStateError("Use the supplier credit note endpoint for a supplier return.")
    if bdr.status != BonDeRetourStatus.confirmed:
        raise BonDeRetourStateError("Confirm the bon de retour before creating an avoir.")
    if bdr.credit_note_id is not None:
        raise BonDeRetourStateError("An avoir is already linked to this bon de retour.")

    invoice_id = request.invoice_id or bdr.source_invoice_id
    if invoice_id is None:
        raise BonDeRetourStateError(
            "An invoice is required to create a client avoir (provide invoice_id or set source_invoice_id)."
        )
    total = request.total_minor if request.total_minor is not None else bdr.total_minor
    if total < 1:
        raise BonDeRetourStateError("Avoir amount must be at least 1.")

    from app.modules.credit_note import service as cn_service
    from app.modules.credit_note.schemas import CreditNoteCreateRequest

    cn = await cn_service.create_credit_note(
        db,
        request=CreditNoteCreateRequest(
            invoice_id=invoice_id,
            total_minor=total,
            reason=request.reason or bdr.reason or f"Retour {bdr.doc_number or bdr.public_id}",
        ),
        garage_id=garage_id,
        user_id=user_id,
    )
    await cn_service.issue_credit_note(db, cn.id, garage_id, user_id=user_id)

    bdr.credit_note_id = cn.id
    bdr.version += 1
    bdr.updated_by = user_id
    await repo.save(db, bdr)
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    logger.info("bon_de_retour_credit_note_created", bdr_id=bdr.id, credit_note_id=cn.id)
    return await _build_out(db, fresh)


async def create_supplier_credit_note_for_br(
    db: AsyncSession, public_id: str, garage_id: int, *, request: CreateSupplierCreditNoteRequest, user_id: int
) -> BonDeRetourOut:
    """Supplier side — create + issue the minimal avoir fournisseur."""
    bdr = await repo.get_by_public_id(db, public_id, garage_id)
    if not bdr:
        raise BonDeRetourNotFoundError(public_id)
    if bdr.party_type != BonDeRetourPartyType.supplier:
        raise BonDeRetourStateError("Use the client credit note endpoint for a client return.")
    if bdr.status != BonDeRetourStatus.confirmed:
        raise BonDeRetourStateError("Confirm the bon de retour before creating an avoir.")
    if bdr.supplier_credit_note_id is not None:
        raise BonDeRetourStateError("An avoir is already linked to this bon de retour.")

    total_ht = request.total_ht_minor if request.total_ht_minor is not None else bdr.subtotal_minor
    total_ttc = request.total_ttc_minor if request.total_ttc_minor is not None else bdr.total_minor

    scn = SupplierCreditNote(
        public_id=str(uuid.uuid4()),
        garage_id=garage_id,
        supplier_id=bdr.supplier_id,
        supplier_invoice_id=bdr.source_supplier_invoice_id,
        bon_de_retour_id=bdr.id,
        total_ht_minor=total_ht,
        total_ttc_minor=total_ttc,
        reason=request.reason or bdr.reason,
        status=SupplierCreditNoteStatus.issued,
        created_by=user_id,
    )
    await repo.create_supplier_credit_note(db, scn)
    seq = await seq_service.next(db, garage_id=garage_id, doc_type="AF")
    scn.doc_number = seq.formatted
    scn.issued_at = datetime.now(tz=timezone.utc)
    await db.flush()

    bdr.supplier_credit_note_id = scn.id
    bdr.version += 1
    bdr.updated_by = user_id
    await db.commit()
    fresh = await repo.get_by_id(db, bdr.id, garage_id)
    logger.info("bon_de_retour_supplier_credit_note_created", bdr_id=bdr.id, scn_id=scn.id, doc_number=scn.doc_number)
    return await _build_out(db, fresh)


async def get_supplier_credit_note(db: AsyncSession, scn_id: int, garage_id: int) -> SupplierCreditNoteOut:
    scn = await repo.get_supplier_credit_note_by_id(db, scn_id, garage_id)
    if not scn:
        raise SupplierCreditNoteNotFoundError(scn_id)
    return SupplierCreditNoteOut.model_validate(scn)


async def list_supplier_credit_notes(
    db: AsyncSession,
    garage_id: int,
    *,
    status: Optional[SupplierCreditNoteStatus] = None,
    page: int = 1,
    page_size: int = 25,
) -> SupplierCreditNoteListResponse:
    items, total = await repo.list_supplier_credit_notes(
        db, garage_id, status=status, page=page, page_size=page_size
    )

    from app.modules.supplier.models import Supplier

    supplier_ids = list({item.supplier_id for item in items})
    supplier_names: dict[int, str] = {}
    if supplier_ids:
        res = await db.execute(
            select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
        )
        supplier_names = {row[0]: row[1] for row in res.fetchall()}

    br_ids = [item.bon_de_retour_id for item in items if item.bon_de_retour_id]
    br_public_ids: dict[int, str] = {}
    if br_ids:
        res = await db.execute(
            select(BonDeRetour.id, BonDeRetour.public_id).where(BonDeRetour.id.in_(br_ids))
        )
        br_public_ids = {row[0]: row[1] for row in res.fetchall()}

    out_items: list[SupplierCreditNoteOut] = []
    for item in items:
        out = SupplierCreditNoteOut.model_validate(item)
        out.supplier_name = supplier_names.get(item.supplier_id)
        out.bon_de_retour_public_id = br_public_ids.get(item.bon_de_retour_id) if item.bon_de_retour_id else None
        out_items.append(out)

    return SupplierCreditNoteListResponse(items=out_items, total=total, page=page, page_size=page_size)
