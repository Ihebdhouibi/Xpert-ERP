"""Payment service — records payments against invoices."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment.models import Payment, PaymentMethod
from app.modules.payment.schemas import PaymentCreateRequest, PaymentOut

log = structlog.get_logger()


class PaymentError(Exception):
    """Base payment error."""


class InvoiceNotPayableError(PaymentError):
    """Invoice is not in a payable state (must be issued or partial)."""

    def __init__(self, invoice_id: int, status: str) -> None:
        super().__init__(f"Invoice {invoice_id} is not payable (status='{status}').")
        self.invoice_id = invoice_id
        self.status = status


class OverpaymentError(PaymentError):
    """Payment amount exceeds outstanding balance."""

    def __init__(self, invoice_id: int, amount_minor: int, outstanding_minor: int) -> None:
        super().__init__(
            f"Payment {amount_minor} exceeds outstanding {outstanding_minor} on invoice {invoice_id}."
        )
        self.invoice_id = invoice_id
        self.amount_minor = amount_minor
        self.outstanding_minor = outstanding_minor


async def record_payment(
    db: AsyncSession,
    *,
    request: PaymentCreateRequest,
    garage_id: int,
    user_id: int,
) -> PaymentOut:
    """Record a payment against an invoice.

    - Validates invoice is issued or partial.
    - Validates amount <= outstanding.
    - Creates Payment row.
    - Updates invoice.paid_amount_minor, outstanding_minor, and transitions status.
    - Returns PaymentOut.
    """
    from app.modules.invoice import repository as inv_repo
    from app.modules.invoice.models import InvoiceStatus
    from app.modules.payment import repository as pay_repo

    invoice = await inv_repo.get_by_id(db, request.invoice_id, garage_id)
    if not invoice:
        raise PaymentError(f"Invoice {request.invoice_id} not found.")

    if invoice.status not in (InvoiceStatus.issued, InvoiceStatus.partial):
        raise InvoiceNotPayableError(invoice.id, invoice.status.value)

    outstanding = invoice.outstanding_minor
    if request.amount_minor > outstanding:
        raise OverpaymentError(invoice.id, request.amount_minor, outstanding)

    paid_at = request.paid_at or datetime.now(timezone.utc)

    payment = Payment(
        invoice_id=invoice.id,
        garage_id=garage_id,
        amount_minor=request.amount_minor,
        payment_method=request.payment_method,
        paid_at=paid_at,
        reference=request.reference,
        notes=request.notes,
        created_by=user_id,
    )
    await pay_repo.create(db, payment)

    # Update invoice totals
    invoice.paid_amount_minor = (invoice.paid_amount_minor or 0) + request.amount_minor
    invoice.outstanding_minor = invoice.total_minor - invoice.paid_amount_minor
    invoice.updated_by = user_id

    if invoice.outstanding_minor <= 0:
        invoice.status = InvoiceStatus.paid
    else:
        invoice.status = InvoiceStatus.partial

    await db.commit()

    # Re-fetch payment to get server-generated fields
    refreshed = await pay_repo.get_by_id(db, payment.id, garage_id)
    assert refreshed is not None

    log.info(
        "payment_recorded",
        invoice_id=invoice.id,
        garage_id=garage_id,
        amount_minor=request.amount_minor,
        payment_id=refreshed.id,
        new_status=invoice.status.value,
    )

    return PaymentOut.model_validate(refreshed)


async def list_payments(
    db: AsyncSession,
    *,
    invoice_id: int,
    garage_id: int,
) -> Sequence[PaymentOut]:
    """List all payments for a given invoice."""
    from app.modules.invoice import repository as inv_repo
    from app.modules.payment import repository as pay_repo

    invoice = await inv_repo.get_by_id(db, invoice_id, garage_id)
    if not invoice:
        raise PaymentError(f"Invoice {invoice_id} not found.")

    payments = await pay_repo.list_by_invoice(db, invoice_id, garage_id)
    return [PaymentOut.model_validate(p) for p in payments]
