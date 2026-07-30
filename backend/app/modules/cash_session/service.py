"""Cash session service — open, close, Z-report."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_, select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.cash_session import repository as repo
from app.modules.cash_session.models import CashSession, CashSessionStatus
from app.modules.cash_session.schemas import (
    CashSessionListResponse,
    CashSessionOut,
    PaymentMethodTally,
    SessionPaymentOut,
    SessionTransactionOut,
    ZReportData,
)
from app.modules.payment.models import Payment, PaymentMethod

logger = get_logger("cash_session.service")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SessionAlreadyOpenError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class SessionAlreadyClosedError(Exception):
    pass


class ClosingReasonRequiredError(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _compute_tallies(
    db: AsyncSession, session_id: int
) -> tuple[list[PaymentMethodTally], int]:
    """Aggregate payments by method for a given session."""
    result = await db.execute(
        select(
            Payment.payment_method,
            sqlfunc.count(Payment.id).label("cnt"),
            sqlfunc.coalesce(sqlfunc.sum(Payment.amount_minor), 0).label("total"),
        )
        .where(Payment.cash_session_id == session_id)
        .group_by(Payment.payment_method)
    )
    rows = result.all()

    tallies = [
        PaymentMethodTally(
            payment_method=row.payment_method,
            count=row.cnt,
            total_minor=row.total,
        )
        for row in rows
    ]
    total_all = sum(t.total_minor for t in tallies)
    return tallies, total_all


async def _sum_cash_payments(db: AsyncSession, session_id: int) -> int:
    """Sum of cash-method payments recorded against this session."""
    result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(Payment.amount_minor), 0)).where(
            Payment.cash_session_id == session_id,
            Payment.payment_method == PaymentMethod.cash,
        )
    )
    return int(result.scalar_one())


async def _sum_cash_advances(db: AsyncSession, session: CashSession) -> int:
    """Sum of cash-method advance payments attributed to this session.

    Advances carry no session FK on legacy rows, so they're attributed by the
    same FK-or-time-window rule used in ``list_session_transactions``.
    """
    from app.modules.advance_payment.models import AdvancePayment

    window_end = session.closed_at or datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(AdvancePayment.amount_minor), 0)).where(
            AdvancePayment.garage_id == session.garage_id,
            AdvancePayment.payment_method == PaymentMethod.cash,
            or_(
                AdvancePayment.cash_session_id == session.id,
                and_(
                    AdvancePayment.cash_session_id.is_(None),
                    AdvancePayment.paid_at >= session.opened_at,
                    AdvancePayment.paid_at <= window_end,
                ),
            ),
        )
    )
    return int(result.scalar_one())


async def _sum_cash_refunds(db: AsyncSession, session: CashSession) -> int:
    """Sum of cash-method refunds attributed to this session (money out)."""
    from app.modules.credit_note.models import Refund

    window_end = session.closed_at or datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(Refund.amount_minor), 0)).where(
            Refund.garage_id == session.garage_id,
            Refund.payment_method == PaymentMethod.cash,
            or_(
                Refund.cash_session_id == session.id,
                and_(
                    Refund.cash_session_id.is_(None),
                    Refund.refunded_at >= session.opened_at,
                    Refund.refunded_at <= window_end,
                ),
            ),
        )
    )
    return int(result.scalar_one())


async def _sum_cash_supplier_payments(db: AsyncSession, session_id: int) -> int:
    """Sum of cash-method supplier invoice payments recorded against this session (money out)."""
    from app.modules.supplier_invoice.models import SupplierInvoice

    result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(SupplierInvoice.paid_amount_minor), 0)).where(
            SupplierInvoice.cash_session_id == session_id,
            SupplierInvoice.payment_method == PaymentMethod.cash,
        )
    )
    return int(result.scalar_one())


async def _expected_cash(db: AsyncSession, session: CashSession) -> int:
    """Expected physical cash = opening float + cash in (payments, advances)
    minus cash out (refunds, supplier invoice payments)."""
    cash_in = await _sum_cash_payments(db, session.id)
    cash_advances = await _sum_cash_advances(db, session)
    cash_refunds = await _sum_cash_refunds(db, session)
    cash_supplier_payments = await _sum_cash_supplier_payments(db, session.id)
    return (
        session.opening_float
        + cash_in
        + cash_advances
        - cash_refunds
        - cash_supplier_payments
    )


async def _to_out(db: AsyncSession, session: CashSession) -> CashSessionOut:
    """Serialize a session, filling the live `expected_cash_so_far` field."""
    out = CashSessionOut.model_validate(session)
    if session.status == CashSessionStatus.open:
        out.expected_cash_so_far = await _expected_cash(db, session)
    else:
        out.expected_cash_so_far = session.expected_total_cash
    return out


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


async def open_session(
    db: AsyncSession,
    *,
    garage_id: int,
    user_id: int,
    opening_float: int = 0,
) -> CashSessionOut:
    logger.info("open_session_start", garage_id=garage_id, user_id=user_id)
    existing = await repo.get_open_session(db, garage_id)
    if existing:
        raise SessionAlreadyOpenError(
            f"A cash session is already open (id={existing.id})."
        )

    session = CashSession(
        garage_id=garage_id,
        status=CashSessionStatus.open,
        opened_at=datetime.now(tz=timezone.utc),
        opened_by_id=user_id,
        opening_float=opening_float,
    )
    await repo.create(db, session)
    await db.commit()

    fresh = await repo.get_by_id(db, session.id, garage_id)
    logger.info(
        "cash_session_opened",
        session_id=session.id,
        garage_id=garage_id,
        opening_float=opening_float,
    )
    return await _to_out(db, fresh)


async def close_session(
    db: AsyncSession,
    *,
    session_id: int,
    garage_id: int,
    user_id: int,
    counted_total_cash: int,
    closing_reason: Optional[str] = None,
) -> CashSessionOut:
    logger.info("close_session_start", session_id=session_id, garage_id=garage_id, user_id=user_id)
    settings = get_settings()
    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)
    if session.status == CashSessionStatus.closed:
        raise SessionAlreadyClosedError(session_id)

    # Expected drawer cash = opening float + cash payments taken in this session
    expected = await _expected_cash(db, session)

    difference = counted_total_cash - expected

    if difference != 0 and settings.cash_diff_require_reason and not closing_reason:
        raise ClosingReasonRequiredError(
            f"A closing reason is required when the difference is non-zero (difference={difference})."
        )

    session.status = CashSessionStatus.closed
    session.closed_at = datetime.now(tz=timezone.utc)
    session.closed_by_id = user_id
    session.expected_total_cash = expected
    session.counted_total_cash = counted_total_cash
    session.difference = difference
    session.closing_reason = closing_reason

    await repo.save(db, session)
    await db.commit()

    fresh = await repo.get_by_id(db, session_id, garage_id)
    logger.info(
        "cash_session_closed",
        session_id=session_id,
        difference=difference,
        garage_id=garage_id,
    )
    return await _to_out(db, fresh)


async def get_session(
    db: AsyncSession, session_id: int, garage_id: int
) -> CashSessionOut:
    logger.info("get_session_start", session_id=session_id, garage_id=garage_id)
    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)
    return await _to_out(db, session)


async def get_current_open_session(
    db: AsyncSession, garage_id: int
) -> Optional[CashSessionOut]:
    logger.info("get_current_open_session_start", garage_id=garage_id)
    session = await repo.get_open_session(db, garage_id)
    if not session:
        return None
    return await _to_out(db, session)


async def list_sessions(
    db: AsyncSession,
    garage_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
) -> CashSessionListResponse:
    logger.info("list_sessions_start", garage_id=garage_id, page=page)
    items, total = await repo.list_by_garage(db, garage_id, page=page, page_size=page_size)
    return CashSessionListResponse(
        items=[await _to_out(db, s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_session_payments(
    db: AsyncSession, session_id: int, garage_id: int
) -> list[SessionPaymentOut]:
    """Return all payments for a session enriched with invoice number and customer name."""
    from app.modules.invoice.models import Invoice
    from app.modules.customer.models import Customer
    from app.modules.auth.models import AppUser

    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)

    stmt = (
        select(
            Payment.id,
            Payment.paid_at,
            Payment.amount_minor,
            Payment.payment_method,
            Payment.reference,
            Payment.notes,
            Payment.invoice_id,
            Payment.created_by,
            Invoice.doc_number.label("invoice_number"),
            Customer.full_name.label("customer_name"),
        )
        .join(Invoice, Invoice.id == Payment.invoice_id, isouter=True)
        .join(Customer, Customer.id == Invoice.customer_id, isouter=True)
        .where(Payment.cash_session_id == session_id)
        .order_by(Payment.paid_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    creator_ids = {r.created_by for r in rows if r.created_by}
    creator_names: dict[int, str] = {}
    if creator_ids:
        users = (await db.execute(
            select(AppUser.id, AppUser.full_name).where(AppUser.id.in_(creator_ids))
        )).all()
        creator_names = {u.id: u.full_name for u in users}

    return [
        SessionPaymentOut(
            id=r.id,
            paid_at=r.paid_at,
            amount_minor=r.amount_minor,
            payment_method=r.payment_method,
            reference=r.reference,
            notes=r.notes,
            invoice_id=r.invoice_id,
            invoice_number=r.invoice_number,
            customer_name=r.customer_name,
            created_by_name=creator_names.get(r.created_by) if r.created_by else None,
        )
        for r in rows
    ]


async def list_session_transactions(
    db: AsyncSession, session_id: int, garage_id: int
) -> list[SessionTransactionOut]:
    """Return every cash movement tied to a session: payments and advances (in)
    plus refunds (out).

    Payments are linked to the session by ``cash_session_id``. Refunds and
    advance payments carry no session FK, so they are attributed by time window
    (between the session's open and close, or now for an open session). Since a
    garage has at most one open session at a time, these windows never overlap.
    """
    from app.modules.invoice.models import Invoice
    from app.modules.customer.models import Customer
    from app.modules.auth.models import AppUser
    from app.modules.credit_note.models import Refund
    from app.modules.advance_payment.models import AdvancePayment

    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)

    window_start = session.opened_at
    window_end = session.closed_at or datetime.now(tz=timezone.utc)

    transactions: list[SessionTransactionOut] = []
    creator_ids: set[int] = set()

    # --- Payments (money in) — authoritative link via cash_session_id ---------
    pay_rows = (await db.execute(
        select(
            Payment.id,
            Payment.paid_at,
            Payment.amount_minor,
            Payment.payment_method,
            Payment.reference,
            Payment.invoice_id,
            Payment.created_by,
            Invoice.doc_number.label("invoice_number"),
            Invoice.public_id.label("invoice_public_id"),
            Customer.full_name.label("customer_name"),
            Customer.public_id.label("customer_public_id"),
        )
        .join(Invoice, Invoice.id == Payment.invoice_id, isouter=True)
        .join(Customer, Customer.id == Invoice.customer_id, isouter=True)
        .where(Payment.cash_session_id == session_id)
    )).all()
    for r in pay_rows:
        if r.created_by:
            creator_ids.add(r.created_by)
        transactions.append(
            SessionTransactionOut(
                kind="payment",
                direction="in",
                id=r.id,
                occurred_at=r.paid_at,
                amount_minor=r.amount_minor,
                payment_method=r.payment_method,
                reference=r.reference,
                label="Paiement facture",
                customer_name=r.customer_name,
                invoice_id=r.invoice_id,
                invoice_number=r.invoice_number,
                invoice_public_id=str(r.invoice_public_id) if r.invoice_public_id else None,
                customer_public_id=str(r.customer_public_id) if r.customer_public_id else None,
                created_by_name=None,
            )
        )

    # --- Refunds (money out) — attributed by time window ----------------------
    refund_rows = (await db.execute(
        select(
            Refund.id,
            Refund.refunded_at,
            Refund.amount_minor,
            Refund.payment_method,
            Refund.reference,
            Refund.credit_note_id,
            Refund.created_by,
            Payment.invoice_id.label("invoice_id"),
            Invoice.doc_number.label("invoice_number"),
            Invoice.public_id.label("invoice_public_id"),
            Customer.full_name.label("customer_name"),
            Customer.public_id.label("customer_public_id"),
        )
        .join(Payment, Payment.id == Refund.payment_id, isouter=True)
        .join(Invoice, Invoice.id == Payment.invoice_id, isouter=True)
        .join(Customer, Customer.id == Invoice.customer_id, isouter=True)
        .where(
            Refund.garage_id == garage_id,
            or_(
                Refund.cash_session_id == session_id,
                and_(
                    Refund.cash_session_id.is_(None),
                    Refund.refunded_at >= window_start,
                    Refund.refunded_at <= window_end,
                ),
            ),
        )
    )).all()
    for r in refund_rows:
        if r.created_by:
            creator_ids.add(r.created_by)
        transactions.append(
            SessionTransactionOut(
                kind="refund",
                direction="out",
                id=r.id,
                occurred_at=r.refunded_at,
                amount_minor=r.amount_minor,
                payment_method=r.payment_method,
                reference=r.reference,
                label="Remboursement",
                customer_name=r.customer_name,
                invoice_id=r.invoice_id,
                invoice_number=r.invoice_number,
                invoice_public_id=str(r.invoice_public_id) if r.invoice_public_id else None,
                credit_note_id=r.credit_note_id,
                customer_public_id=str(r.customer_public_id) if r.customer_public_id else None,
                created_by_name=None,
            )
        )

    # --- Advance payments (money in) — attributed by time window --------------
    advance_rows = (await db.execute(
        select(
            AdvancePayment.id,
            AdvancePayment.paid_at,
            AdvancePayment.amount_minor,
            AdvancePayment.payment_method,
            AdvancePayment.reference,
            AdvancePayment.created_by,
            Customer.full_name.label("customer_name"),
            Customer.public_id.label("customer_public_id"),
        )
        .join(Customer, Customer.id == AdvancePayment.customer_id, isouter=True)
        .where(
            AdvancePayment.garage_id == garage_id,
            or_(
                AdvancePayment.cash_session_id == session_id,
                and_(
                    AdvancePayment.cash_session_id.is_(None),
                    AdvancePayment.paid_at >= window_start,
                    AdvancePayment.paid_at <= window_end,
                ),
            ),
        )
    )).all()
    for r in advance_rows:
        if r.created_by:
            creator_ids.add(r.created_by)
        transactions.append(
            SessionTransactionOut(
                kind="advance",
                direction="in",
                id=r.id,
                occurred_at=r.paid_at,
                amount_minor=r.amount_minor,
                payment_method=r.payment_method,
                reference=r.reference,
                label="Acompte client",
                customer_name=r.customer_name,
                customer_public_id=str(r.customer_public_id) if r.customer_public_id else None,
                created_by_name=None,
            )
        )

    # --- Supplier invoice payments (money out) — authoritative link via cash_session_id ---
    from app.modules.supplier_invoice.models import SupplierInvoice
    from app.modules.supplier.models import Supplier

    supplier_rows = (await db.execute(
        select(
            SupplierInvoice.id,
            SupplierInvoice.paid_at,
            SupplierInvoice.paid_amount_minor,
            SupplierInvoice.payment_method,
            SupplierInvoice.number,
            SupplierInvoice.created_by,
            Supplier.name.label("supplier_name"),
        )
        .join(Supplier, Supplier.id == SupplierInvoice.supplier_id, isouter=True)
        .where(SupplierInvoice.cash_session_id == session_id)
    )).all()
    for r in supplier_rows:
        if r.created_by:
            creator_ids.add(r.created_by)
        transactions.append(
            SessionTransactionOut(
                kind="supplier_payment",
                direction="out",
                id=r.id,
                occurred_at=r.paid_at,
                amount_minor=r.paid_amount_minor,
                payment_method=r.payment_method,
                label="Paiement fournisseur",
                supplier_name=r.supplier_name,
                supplier_invoice_number=r.number,
                created_by_name=None,
            )
        )

    # Resolve creator names in a single batch.
    if creator_ids:
        users = (await db.execute(
            select(AppUser.id, AppUser.full_name).where(AppUser.id.in_(creator_ids))
        )).all()
        creator_names = {u.id: u.full_name for u in users}
        for t, src in zip(
            transactions,
            [*pay_rows, *refund_rows, *advance_rows, *supplier_rows],
        ):
            t.created_by_name = creator_names.get(src.created_by) if src.created_by else None

    transactions.sort(key=lambda t: t.occurred_at, reverse=True)
    return transactions


async def get_z_report_data(
    db: AsyncSession, session_id: int, garage_id: int
) -> ZReportData:
    logger.info("get_z_report_data_start", session_id=session_id, garage_id=garage_id)
    session = await repo.get_by_id(db, session_id, garage_id)
    if not session:
        raise SessionNotFoundError(session_id)

    tallies, total_all = await _compute_tallies(db, session_id)

    return ZReportData(
        session_id=session.id,
        garage_id=session.garage_id,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        opened_by_id=session.opened_by_id,
        closed_by_id=session.closed_by_id,
        tallies=tallies,
        expected_total_cash=session.expected_total_cash,
        counted_total_cash=session.counted_total_cash,
        difference=session.difference,
        closing_reason=session.closing_reason,
        total_all_methods=total_all,
    )


async def generate_z_report_pdf(
    db: AsyncSession, session_id: int, garage_id: int
) -> bytes:
    """Render Z-report as PDF bytes using WeasyPrint."""
    logger.info("generate_z_report_pdf_start", session_id=session_id, garage_id=garage_id)
    from app.core.config import get_settings
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    import weasyprint

    data = await get_z_report_data(db, session_id, garage_id)
    settings = get_settings()

    template_dir = Path(__file__).parent.parent.parent.parent / "templates" / "documents"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("z_report.html")

    html_str = template.render(
        data=data,
        cfg=settings,
    )

    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(
        None,
        lambda: weasyprint.HTML(string=html_str).write_pdf(),
    )
    return pdf_bytes
