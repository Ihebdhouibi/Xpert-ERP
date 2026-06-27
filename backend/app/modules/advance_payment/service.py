"""Advance payment service — record deposits and auto-deduct on invoice issuance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.advance_payment import repository as repo
from app.modules.advance_payment.models import AdvancePayment
from app.modules.advance_payment.schemas import (
    AdvancePaymentCreateRequest,
    AdvancePaymentListResponse,
    AdvancePaymentOut,
)

logger = get_logger("advance_payment.service")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AdvancePaymentError(Exception):
    pass


class CustomerNotFoundError(Exception):
    pass


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

async def record_advance(
    db: AsyncSession,
    *,
    request: AdvancePaymentCreateRequest,
    garage_id: int,
    user_id: int,
) -> AdvancePaymentOut:
    """Record a deposit/advance payment for a customer before an invoice exists."""
    logger.info("record_advance_start", customer_id=request.customer_id, garage_id=garage_id)
    # Validate customer belongs to this garage
    from app.modules.customer import repository as customer_repo
    customer = await customer_repo.get_by_id(db, garage_id, request.customer_id)
    if not customer:
        raise CustomerNotFoundError(request.customer_id)

    advance = AdvancePayment(
        garage_id=garage_id,
        customer_id=request.customer_id,
        repair_order_id=request.repair_order_id,
        amount_minor=request.amount_minor,
        payment_method=request.payment_method,
        paid_at=request.paid_at or datetime.now(tz=timezone.utc),
        reference=request.reference,
        notes=request.notes,
        applied_to_invoice_id=None,
        applied_at=None,
        created_by=user_id,
    )
    await repo.create(db, advance)
    await db.commit()

    fresh = await repo.get_by_id(db, advance.id, garage_id)
    logger.info(
        "advance_payment_recorded",
        advance_id=advance.id,
        customer_id=request.customer_id,
        amount_minor=request.amount_minor,
        garage_id=garage_id,
    )
    return AdvancePaymentOut.model_validate(fresh)


async def apply_advances_to_invoice(
    db: AsyncSession,
    *,
    invoice_id: int,
    customer_id: int,
    garage_id: int,
) -> int:
    """Apply unapplied advance payments to an invoice.

    Must be called BEFORE db.commit() in the issue_invoice flow so all changes
    are committed atomically.  Returns total amount applied (minor units).
    """
    logger.info("apply_advances_start", invoice_id=invoice_id, customer_id=customer_id, garage_id=garage_id)
    from app.modules.invoice import repository as invoice_repo

    invoice = await invoice_repo.get_by_id(db, invoice_id, garage_id)
    if not invoice:
        return 0

    advances = await repo.list_unapplied_by_customer(db, customer_id, garage_id)
    if not advances:
        return 0

    now = datetime.now(tz=timezone.utc)
    total_applied = 0

    for advance in advances:
        outstanding = invoice.outstanding_minor
        if outstanding <= 0:
            break

        apply_amount = min(advance.amount_minor, outstanding)
        # Mark advance as applied
        advance.applied_to_invoice_id = invoice_id
        advance.applied_at = now
        advance.applied_amount_minor = apply_amount
        db.add(advance)

        # Reduce invoice outstanding
        paid = (invoice.paid_amount_minor or 0) + apply_amount
        invoice.paid_amount_minor = paid
        invoice.outstanding_minor = invoice.total_minor - paid

        # Update invoice status
        from app.modules.invoice.models import InvoiceStatus
        if invoice.outstanding_minor <= 0:
            invoice.status = InvoiceStatus.paid
        else:
            invoice.status = InvoiceStatus.partial

        total_applied += apply_amount
        logger.info(
            "advance_applied",
            advance_id=advance.id,
            invoice_id=invoice_id,
            amount_minor=apply_amount,
        )

    if total_applied:
        db.add(invoice)

    return total_applied


async def _enrich_advances(
    db: AsyncSession,
    advances: list,
    garage_id: int,
) -> list[AdvancePaymentOut]:
    """Resolve customer names and invoice public_ids for a list of advance ORM objects."""
    from sqlalchemy import select as sa_select
    from app.modules.customer.models import Customer
    from app.modules.invoice.models import Invoice

    items = [AdvancePaymentOut.model_validate(a) for a in advances]

    # Batch-fetch distinct customers
    customer_ids = list({a.customer_id for a in advances})
    if customer_ids:
        cust_result = await db.execute(
            sa_select(Customer.id, Customer.full_name, Customer.company_name)
            .where(Customer.id.in_(customer_ids), Customer.garage_id == garage_id)
        )
        cust_map: dict[int, str] = {}
        for cid, full_name, company_name in cust_result:
            cust_map[cid] = f"{full_name} ({company_name})" if company_name else full_name
        for it in items:
            it.customer_name = cust_map.get(it.customer_id)

    # Batch-fetch invoice public_ids for applied advances
    invoice_ids = list({a.applied_to_invoice_id for a in advances if a.applied_to_invoice_id})
    if invoice_ids:
        inv_result = await db.execute(
            sa_select(Invoice.id, Invoice.public_id)
            .where(Invoice.id.in_(invoice_ids), Invoice.garage_id == garage_id)
        )
        inv_map: dict[int, str] = {iid: pub for iid, pub in inv_result}
        for it in items:
            if it.applied_to_invoice_id:
                it.applied_invoice_public_id = inv_map.get(it.applied_to_invoice_id)

    return items


async def list_advances(
    db: AsyncSession,
    *,
    customer_id: int,
    garage_id: int,
) -> AdvancePaymentListResponse:
    advances = await repo.list_by_customer(db, customer_id, garage_id)
    items = await _enrich_advances(db, advances, garage_id)
    return AdvancePaymentListResponse(items=items, total=len(items))


async def list_all_advances(
    db: AsyncSession,
    *,
    garage_id: int,
    status: str | None = None,
) -> AdvancePaymentListResponse:
    """List all advance payments for the garage with optional status filter."""
    advances = await repo.list_all_by_garage(db, garage_id, status=status)
    items = await _enrich_advances(db, advances, garage_id)
    return AdvancePaymentListResponse(items=items, total=len(items))


async def list_advances_by_invoice(
    db: AsyncSession,
    *,
    invoice_id: int,
    garage_id: int,
) -> AdvancePaymentListResponse:
    """List advances applied to a specific invoice."""
    advances = await repo.list_by_invoice(db, invoice_id, garage_id)
    items = await _enrich_advances(db, advances, garage_id)
    return AdvancePaymentListResponse(items=items, total=len(items))
