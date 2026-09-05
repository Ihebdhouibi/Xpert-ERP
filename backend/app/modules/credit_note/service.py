"""Credit note and refund service — business logic."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.credit_note import repository as repo
from app.modules.credit_note.models import CreditNote, CreditNoteStatus, Refund
from app.modules.credit_note.schemas import (
    CreditNoteCreateRequest,
    CreditNoteListResponse,
    CreditNoteOut,
    RefundCreateRequest,
    RefundOut,
)
from app.modules.payment.models import PaymentMethod
from app.modules.sequence import service as seq_service

logger = get_logger("credit_note.service")


def _build_cn_out(cn: CreditNote) -> CreditNoteOut:
    """Validate ORM → schema and populate denormalised invoice fields."""
    out = CreditNoteOut.model_validate(cn)
    inv = getattr(cn, "invoice", None)
    if inv is not None:
        out.invoice_doc_number = inv.doc_number
        out.invoice_public_id = inv.public_id
        out.invoice_total_minor = inv.total_minor
        out.invoice_paid_amount_minor = inv.paid_amount_minor
    return out


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CreditNoteNotFoundError(Exception):
    pass


class CreditNoteStateError(Exception):
    pass


class RefundNotFoundError(Exception):
    pass


class RefundExceedsPaymentError(Exception):
    """Requested refund exceeds the net refundable amount of the payment."""

    def __init__(self, payment_id: int, requested: int, available: int) -> None:
        super().__init__(
            f"Refund of {requested} exceeds available {available} on payment {payment_id}."
        )
        self.payment_id = payment_id
        self.requested = requested
        self.available = available


# ---------------------------------------------------------------------------
# Credit note CRUD
# ---------------------------------------------------------------------------


async def create_credit_note(
    db: AsyncSession,
    *,
    request: CreditNoteCreateRequest,
    garage_id: int,
    user_id: int,
) -> CreditNoteOut:
    """Create a draft credit note against an invoice."""
    logger.info("create_credit_note_start", invoice_id=request.invoice_id, garage_id=garage_id)
    from app.modules.invoice import repository as inv_repo
    from app.modules.invoice.models import InvoiceStatus
    from app.modules.invoice.service import InvoiceNotFoundError

    inv = await inv_repo.get_by_id(db, request.invoice_id, garage_id)
    if not inv:
        raise InvoiceNotFoundError(request.invoice_id)
    # Allow creating against issued / partial / paid (not draft / cancelled)
    if inv.status not in (InvoiceStatus.issued, InvoiceStatus.partial, InvoiceStatus.paid):
        raise CreditNoteStateError(
            f"Cannot create credit note for invoice in status '{inv.status.value}'."
        )

    cn = CreditNote(
        garage_id=garage_id,
        invoice_id=request.invoice_id,
        total_minor=request.total_minor,
        reason=request.reason,
        status=CreditNoteStatus.draft,
        created_by=user_id,
    )
    await repo.create_credit_note(db, cn)
    await db.commit()

    fresh = await repo.get_credit_note_by_id(db, cn.id, garage_id)
    logger.info("credit_note_created", cn_id=cn.id, invoice_id=request.invoice_id)
    return _build_cn_out(fresh)


async def _auto_create_and_issue_credit_note(
    db: AsyncSession,
    *,
    invoice_id: int,
    garage_id: int,
    total_minor: int,
    reason: Optional[str],
    user_id: int,
) -> CreditNote:
    """Internal: create + immediately issue a credit note (used by cancel_invoice)."""
    cn = CreditNote(
        garage_id=garage_id,
        invoice_id=invoice_id,
        total_minor=total_minor,
        reason=reason,
        status=CreditNoteStatus.draft,
        created_by=user_id,
    )
    await repo.create_credit_note(db, cn)
    await db.flush()

    # Assign doc number + issue
    seq = await seq_service.next(db, garage_id=garage_id, doc_type="CN")
    cn.doc_number = seq.formatted
    cn.status = CreditNoteStatus.issued
    cn.issued_at = datetime.now(tz=timezone.utc)
    await repo.save_credit_note(db, cn)

    logger.info("credit_note_auto_issued", cn_id=cn.id, invoice_id=invoice_id)
    return cn


async def issue_credit_note(
    db: AsyncSession,
    cn_id: int,
    garage_id: int,
    *,
    user_id: int,
) -> CreditNoteOut:
    """DRAFT → ISSUED. Assigns doc_number and posts balance reversal."""
    logger.info("issue_credit_note_start", cn_id=cn_id, garage_id=garage_id)
    cn = await repo.get_credit_note_by_id(db, cn_id, garage_id)
    if not cn:
        raise CreditNoteNotFoundError(cn_id)
    if cn.status != CreditNoteStatus.draft:
        raise CreditNoteStateError(f"Cannot issue credit note in status '{cn.status.value}'.")

    seq = await seq_service.next(db, garage_id=garage_id, doc_type="CN")
    cn.doc_number = seq.formatted
    cn.status = CreditNoteStatus.issued
    cn.issued_at = datetime.now(tz=timezone.utc)
    await repo.save_credit_note(db, cn)

    # Credit note issued → customer outstanding decreases (credit note = garage owes customer)
    from app.modules.invoice import repository as inv_repo
    inv = await inv_repo.get_by_id(db, cn.invoice_id, garage_id)
    if inv:
        from app.modules.customer.credit_service import post_balance_event
        from app.core.config import get_settings
        await post_balance_event(
            db,
            customer_id=inv.customer_id,
            garage_id=garage_id,
            reason="credit_note_issued",
            delta_minor=-cn.total_minor,
            currency=get_settings().credit_currency,
            ref_type="credit_note",
            ref_id=cn.id,
            created_by=user_id,
        )

    await db.commit()

    from app.modules.kpi.service import invalidate_cache as invalidate_kpi_cache
    await invalidate_kpi_cache(garage_id)

    fresh = await repo.get_credit_note_by_id(db, cn.id, garage_id)
    logger.info("credit_note_issued", cn_id=cn_id, doc_number=fresh.doc_number if fresh else None)
    return _build_cn_out(fresh)


async def void_credit_note(
    db: AsyncSession,
    cn_id: int,
    garage_id: int,
    *,
    user_id: int,
) -> CreditNoteOut:
    """ISSUED → VOID. Reverses the balance event."""
    logger.info("void_credit_note_start", cn_id=cn_id, garage_id=garage_id)
    cn = await repo.get_credit_note_by_id(db, cn_id, garage_id)
    if not cn:
        raise CreditNoteNotFoundError(cn_id)
    if cn.status != CreditNoteStatus.issued:
        raise CreditNoteStateError(f"Cannot void credit note in status '{cn.status.value}'.")

    cn.status = CreditNoteStatus.void
    cn.voided_at = datetime.now(tz=timezone.utc)
    await repo.save_credit_note(db, cn)

    # Reverse the credit note balance event
    from app.modules.invoice import repository as inv_repo
    inv = await inv_repo.get_by_id(db, cn.invoice_id, garage_id)
    if inv:
        from app.modules.customer.credit_service import post_balance_event
        from app.core.config import get_settings
        await post_balance_event(
            db,
            customer_id=inv.customer_id,
            garage_id=garage_id,
            reason="credit_note_voided",
            delta_minor=cn.total_minor,
            currency=get_settings().credit_currency,
            ref_type="credit_note",
            ref_id=cn.id,
            created_by=user_id,
        )

    await db.commit()

    from app.modules.kpi.service import invalidate_cache as invalidate_kpi_cache
    await invalidate_kpi_cache(garage_id)

    fresh = await repo.get_credit_note_by_id(db, cn.id, garage_id)
    logger.info("credit_note_voided", cn_id=cn_id)
    return _build_cn_out(fresh)


async def get_credit_note(db: AsyncSession, cn_id: int, garage_id: int) -> CreditNoteOut:
    cn = await repo.get_credit_note_by_id(db, cn_id, garage_id)
    if not cn:
        raise CreditNoteNotFoundError(cn_id)
    return _build_cn_out(cn)


async def list_credit_notes(
    db: AsyncSession,
    garage_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    invoice_id: int | None = None,
) -> CreditNoteListResponse:
    from sqlalchemy import select as sa_select
    from app.modules.customer.models import Customer

    items, total = await repo.list_credit_notes(db, garage_id, page=page, page_size=page_size, invoice_id=invoice_id)

    cust_ids = list({cn.invoice.customer_id for cn in items if getattr(cn, "invoice", None) and cn.invoice.customer_id})
    customers_map: dict[int, str] = {}
    if cust_ids:
        res = await db.execute(sa_select(Customer).where(Customer.id.in_(cust_ids)))
        customers_map = {c.id: c.full_name for c in res.scalars()}

    out_items = []
    for cn in items:
        out = _build_cn_out(cn)
        inv = getattr(cn, "invoice", None)
        if inv and inv.customer_id:
            out.customer_name = customers_map.get(inv.customer_id)
        out_items.append(out)

    return CreditNoteListResponse(items=out_items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------------


async def record_refund(
    db: AsyncSession,
    *,
    request: RefundCreateRequest,
    garage_id: int,
    user_id: int,
) -> RefundOut:
    """Record a refund against an original payment.

    Validates:
    - Payment exists and belongs to this garage.
    - Refund amount ≤ payment amount − already refunded.
    - If credit_note_id given: credit note must exist and be issued.
    """
    logger.info("record_refund_start", payment_id=request.payment_id, garage_id=garage_id)
    from app.modules.payment import repository as pay_repo

    payment = await pay_repo.get_by_id(db, request.payment_id, garage_id)
    if not payment:
        raise RefundNotFoundError(f"Payment {request.payment_id} not found.")
    if payment.is_exported:
        raise CreditNoteStateError(
            "Exported payments cannot be refunded directly. Issue a credit note against the invoice."
        )

    already_refunded = await repo.total_refunded_for_payment(db, request.payment_id)
    available = payment.amount_minor - already_refunded
    if request.amount_minor > available:
        raise RefundExceedsPaymentError(request.payment_id, request.amount_minor, available)

    # Validate credit_note_id if provided
    if request.credit_note_id is not None:
        cn = await repo.get_credit_note_by_id(db, request.credit_note_id, garage_id)
        if not cn:
            raise CreditNoteNotFoundError(request.credit_note_id)
        if cn.status != CreditNoteStatus.issued:
            raise CreditNoteStateError("Only issued credit notes can be linked to a refund.")

    refund = Refund(
        garage_id=garage_id,
        payment_id=request.payment_id,
        credit_note_id=request.credit_note_id,
        amount_minor=request.amount_minor,
        payment_method=request.payment_method,
        reason=request.reason,
        reference=request.reference,
        refunded_at=datetime.now(tz=timezone.utc),
        created_by=user_id,
    )

    # Auto-link to the currently open cash session (if any)
    from app.modules.cash_session import repository as session_repo
    open_session = await session_repo.get_open_session(db, garage_id)
    if open_session:
        refund.cash_session_id = open_session.id

    await repo.create_refund(db, refund)

    # Post credit entry to customer ledger (refund reduces garage's credit to customer)
    from app.modules.invoice import repository as inv_repo
    invoice = await inv_repo.get_by_id(db, payment.invoice_id, garage_id)
    if invoice:
        from app.modules.customer.credit_service import post_balance_event
        from app.core.config import get_settings
        await post_balance_event(
            db,
            customer_id=invoice.customer_id,
            garage_id=garage_id,
            reason="refund_issued",
            delta_minor=request.amount_minor,  # positive: garage paid back → customer balance increases? No—
            # Refund means garage returns money already paid. The customer's outstanding already decreased
            # when payment was recorded (payment_received event). Refund reverses part of that credit.
            # delta_minor = +amount = outstanding goes up again (customer "un-pays" the refunded portion)
            currency=get_settings().credit_currency,
            ref_type="refund",
            ref_id=refund.id,
            created_by=user_id,
        )

    await db.commit()

    from app.modules.kpi.service import invalidate_cache as invalidate_kpi_cache
    await invalidate_kpi_cache(garage_id)

    fresh = await repo.get_refund_by_id(db, refund.id, garage_id)
    logger.info("refund_recorded", refund_id=refund.id, payment_id=request.payment_id)
    return RefundOut.model_validate(fresh)


async def get_refund(db: AsyncSession, refund_id: int, garage_id: int) -> RefundOut:
    r = await repo.get_refund_by_id(db, refund_id, garage_id)
    if not r:
        raise RefundNotFoundError(refund_id)
    return RefundOut.model_validate(r)
