"""Tests for credit note and refund workflow (#35)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password
from app.modules.customer.models import Customer, CustomerStatus, CustomerType
from app.modules.invoice.models import Invoice, InvoiceStatus
from app.modules.payment.models import Payment, PaymentMethod
from app.modules.credit_note.models import CreditNote, CreditNoteStatus, Refund
from app.modules.credit_note import service as cn_svc
from app.modules.credit_note.schemas import (
    CreditNoteCreateRequest,
    RefundCreateRequest,
)
from app.modules.credit_note.service import (
    CreditNoteNotFoundError,
    CreditNoteStateError,
    RefundExceedsPaymentError,
    RefundNotFoundError,
)
from app.modules.invoice import service as inv_svc
from app.modules.payment import service as pay_svc
from app.modules.payment.schemas import PaymentCreateRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_customer(db: AsyncSession, credit_limit: int = 0) -> Customer:
    c = Customer(
        garage_id=1,
        type=CustomerType.individual,
        full_name="CN Test Customer",
        status=CustomerStatus.active,
        credit_limit_minor=credit_limit,
    )
    db.add(c)
    await db.flush()
    return c


async def _make_issued_invoice(
    db: AsyncSession, customer_id: int, total: int = 10000
) -> Invoice:
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.issued,
        doc_number="INV-CN-001",
        subtotal_minor=total,
        discount_minor=0,
        vat_minor=0,
        total_minor=total,
        paid_amount_minor=0,
        outstanding_minor=total,
        issued_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(inv)
    await db.flush()
    return inv


async def _make_paid_invoice(
    db: AsyncSession, customer_id: int, total: int = 10000
) -> tuple[Invoice, Payment]:
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.paid,
        doc_number="INV-CN-002",
        subtotal_minor=total,
        discount_minor=0,
        vat_minor=0,
        total_minor=total,
        paid_amount_minor=total,
        outstanding_minor=0,
        issued_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(inv)
    await db.flush()

    pmt = Payment(
        invoice_id=inv.id,
        garage_id=1,
        amount_minor=total,
        payment_method=PaymentMethod.cash,
        paid_at=datetime.now(timezone.utc),
        created_by=1,
    )
    db.add(pmt)
    await db.flush()
    return inv, pmt


async def _make_partial_invoice(
    db: AsyncSession, customer_id: int, total: int = 10000, paid: int = 5000
) -> tuple[Invoice, Payment]:
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.partial,
        doc_number="INV-CN-003",
        subtotal_minor=total,
        discount_minor=0,
        vat_minor=0,
        total_minor=total,
        paid_amount_minor=paid,
        outstanding_minor=total - paid,
        issued_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(inv)
    await db.flush()

    pmt = Payment(
        invoice_id=inv.id,
        garage_id=1,
        amount_minor=paid,
        payment_method=PaymentMethod.cash,
        paid_at=datetime.now(timezone.utc),
        created_by=1,
    )
    db.add(pmt)
    await db.flush()
    return inv, pmt


async def _make_draft_invoice(db: AsyncSession, customer_id: int, total: int = 5000) -> Invoice:
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.draft,
        subtotal_minor=total,
        discount_minor=0,
        vat_minor=0,
        total_minor=total,
        paid_amount_minor=0,
        outstanding_minor=total,
        version=1,
    )
    db.add(inv)
    await db.flush()
    return inv


# ---------------------------------------------------------------------------
# Credit note CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreditNoteCRUD:
    async def test_create_draft_credit_note(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=5000, reason="overcharge")
        cn_out = await cn_svc.create_credit_note(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert cn_out.status == CreditNoteStatus.draft
        assert cn_out.total_minor == 5000
        assert cn_out.doc_number is None
        assert cn_out.invoice_id == inv.id

    async def test_create_credit_note_on_paid_invoice(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv, _ = await _make_paid_invoice(db_session, customer.id)

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=3000)
        cn_out = await cn_svc.create_credit_note(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert cn_out.status == CreditNoteStatus.draft

    async def test_create_credit_note_on_draft_invoice_fails(
        self, db_session: AsyncSession
    ) -> None:
        customer = await _make_customer(db_session)
        inv = await _make_draft_invoice(db_session, customer.id)

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=1000)
        with pytest.raises(CreditNoteStateError):
            await cn_svc.create_credit_note(
                db_session, request=req, garage_id=1, user_id=1
            )

    async def test_issue_credit_note_assigns_doc_number(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)
        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=2000)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)

        issued = await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)
        assert issued.status == CreditNoteStatus.issued
        assert issued.doc_number is not None
        assert issued.issued_at is not None

    async def test_issue_already_issued_fails(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)
        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=2000)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)
        await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)

        with pytest.raises(CreditNoteStateError):
            await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)

    async def test_void_issued_credit_note(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)
        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=4000)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)
        await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)

        voided = await cn_svc.void_credit_note(db_session, cn.id, 1, user_id=1)
        assert voided.status == CreditNoteStatus.void
        assert voided.voided_at is not None

    async def test_void_draft_credit_note_fails(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)
        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=1000)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)

        with pytest.raises(CreditNoteStateError):
            await cn_svc.void_credit_note(db_session, cn.id, 1, user_id=1)

    async def test_get_credit_note_not_found_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(CreditNoteNotFoundError):
            await cn_svc.get_credit_note(db_session, 99999, 1)

    async def test_list_credit_notes_empty(self, db_session: AsyncSession) -> None:
        result = await cn_svc.list_credit_notes(db_session, garage_id=99)
        assert result.total == 0
        assert result.items == []


# ---------------------------------------------------------------------------
# Credit note balance ledger integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreditNoteBalanceLedger:
    async def test_issue_credit_note_decreases_outstanding(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.customer import repository as cust_repo

        customer = await _make_customer(db_session)
        customer.outstanding_minor = 8000
        inv = await _make_issued_invoice(db_session, customer.id)
        await db_session.flush()

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=3000)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)
        await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)

        fresh = await cust_repo.get_by_id(db_session, 1, customer.id)
        assert fresh.outstanding_minor == 5000

    async def test_void_credit_note_reverses_outstanding(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.customer import repository as cust_repo

        customer = await _make_customer(db_session)
        customer.outstanding_minor = 8000
        inv = await _make_issued_invoice(db_session, customer.id)
        await db_session.flush()

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=3000)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)
        await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)
        await cn_svc.void_credit_note(db_session, cn.id, 1, user_id=1)

        fresh = await cust_repo.get_by_id(db_session, 1, customer.id)
        assert fresh.outstanding_minor == 8000

    async def test_issue_posts_credit_note_issued_event(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=2500)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)
        await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)

        events = (await db_session.execute(
            select(CustomerBalanceEvent)
            .where(
                CustomerBalanceEvent.customer_id == customer.id,
                CustomerBalanceEvent.reason == "credit_note_issued",
            )
        )).scalars().all()
        assert len(events) == 1
        assert events[0].delta_minor == -2500

    async def test_void_posts_credit_note_voided_event(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id)

        req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=1500)
        cn = await cn_svc.create_credit_note(db_session, request=req, garage_id=1, user_id=1)
        await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)
        await cn_svc.void_credit_note(db_session, cn.id, 1, user_id=1)

        events = (await db_session.execute(
            select(CustomerBalanceEvent)
            .where(
                CustomerBalanceEvent.customer_id == customer.id,
                CustomerBalanceEvent.reason == "credit_note_voided",
            )
        )).scalars().all()
        assert len(events) == 1
        assert events[0].delta_minor == 1500


# ---------------------------------------------------------------------------
# Auto credit note on invoice cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAutoCreditNoteOnCancel:
    async def test_cancel_paid_invoice_auto_creates_credit_note(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.credit_note import repository as cn_repo

        customer = await _make_customer(db_session)
        inv, _ = await _make_paid_invoice(db_session, customer.id, total=8000)

        # Bump version for cancel (paid invoice = version from creation)
        await inv_svc.cancel_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        cns = await cn_repo.list_credit_notes_by_invoice(db_session, inv.id, 1)
        assert len(cns) == 1
        assert cns[0].status == CreditNoteStatus.issued
        assert cns[0].total_minor == 8000  # full paid amount

    async def test_cancel_partial_invoice_auto_creates_credit_note_for_paid_amount(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.credit_note import repository as cn_repo

        customer = await _make_customer(db_session)
        inv, _ = await _make_partial_invoice(
            db_session, customer.id, total=10000, paid=4000
        )

        await inv_svc.cancel_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        cns = await cn_repo.list_credit_notes_by_invoice(db_session, inv.id, 1)
        assert len(cns) == 1
        assert cns[0].total_minor == 4000  # only the paid portion

    async def test_cancel_issued_unpaid_invoice_no_credit_note(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.credit_note import repository as cn_repo

        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id, total=6000)

        await inv_svc.cancel_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        cns = await cn_repo.list_credit_notes_by_invoice(db_session, inv.id, 1)
        assert len(cns) == 0

    async def test_cancel_draft_invoice_no_credit_note(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.credit_note import repository as cn_repo

        customer = await _make_customer(db_session)
        inv = await _make_draft_invoice(db_session, customer.id)

        await inv_svc.cancel_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        cns = await cn_repo.list_credit_notes_by_invoice(db_session, inv.id, 1)
        assert len(cns) == 0

    async def test_auto_credit_note_has_cn_doc_number(self, db_session: AsyncSession) -> None:
        from app.modules.credit_note import repository as cn_repo

        customer = await _make_customer(db_session)
        inv, _ = await _make_paid_invoice(db_session, customer.id, total=5000)
        await inv_svc.cancel_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        cns = await cn_repo.list_credit_notes_by_invoice(db_session, inv.id, 1)
        assert cns[0].doc_number is not None
        assert "CN" in cns[0].doc_number


# ---------------------------------------------------------------------------
# Refund tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefund:
    async def test_record_refund_success(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=10000)

        req = RefundCreateRequest(
            payment_id=pmt.id, amount_minor=3000, payment_method=PaymentMethod.cash,
            reason="customer dissatisfied",
        )
        refund_out = await cn_svc.record_refund(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert refund_out.amount_minor == 3000
        assert refund_out.payment_id == pmt.id
        assert refund_out.payment_method == PaymentMethod.cash

    async def test_full_refund_success(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=5000)

        req = RefundCreateRequest(payment_id=pmt.id, amount_minor=5000)
        refund_out = await cn_svc.record_refund(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert refund_out.amount_minor == 5000

    async def test_refund_exceeds_payment_raises(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=5000)

        req = RefundCreateRequest(payment_id=pmt.id, amount_minor=6000)
        with pytest.raises(RefundExceedsPaymentError) as exc_info:
            await cn_svc.record_refund(db_session, request=req, garage_id=1, user_id=1)
        assert exc_info.value.available == 5000

    async def test_partial_refund_then_another_partial_refund(
        self, db_session: AsyncSession
    ) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=10000)

        req1 = RefundCreateRequest(payment_id=pmt.id, amount_minor=4000)
        await cn_svc.record_refund(db_session, request=req1, garage_id=1, user_id=1)

        req2 = RefundCreateRequest(payment_id=pmt.id, amount_minor=4000)
        refund2 = await cn_svc.record_refund(db_session, request=req2, garage_id=1, user_id=1)
        assert refund2.amount_minor == 4000

    async def test_over_refund_after_partial_raises(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=10000)

        req1 = RefundCreateRequest(payment_id=pmt.id, amount_minor=8000)
        await cn_svc.record_refund(db_session, request=req1, garage_id=1, user_id=1)

        req2 = RefundCreateRequest(payment_id=pmt.id, amount_minor=3000)
        with pytest.raises(RefundExceedsPaymentError) as exc_info:
            await cn_svc.record_refund(db_session, request=req2, garage_id=1, user_id=1)
        assert exc_info.value.available == 2000

    async def test_refund_links_to_credit_note(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=10000)

        # Create and issue credit note
        cn_req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=3000)
        cn = await cn_svc.create_credit_note(
            db_session, request=cn_req, garage_id=1, user_id=1
        )
        issued_cn = await cn_svc.issue_credit_note(db_session, cn.id, 1, user_id=1)

        req = RefundCreateRequest(
            payment_id=pmt.id, amount_minor=3000, credit_note_id=issued_cn.id
        )
        refund = await cn_svc.record_refund(db_session, request=req, garage_id=1, user_id=1)
        assert refund.credit_note_id == issued_cn.id

    async def test_refund_linked_to_draft_credit_note_fails(
        self, db_session: AsyncSession
    ) -> None:
        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=10000)

        cn_req = CreditNoteCreateRequest(invoice_id=inv.id, total_minor=2000)
        cn = await cn_svc.create_credit_note(
            db_session, request=cn_req, garage_id=1, user_id=1
        )

        req = RefundCreateRequest(
            payment_id=pmt.id, amount_minor=2000, credit_note_id=cn.id
        )
        with pytest.raises(CreditNoteStateError):
            await cn_svc.record_refund(db_session, request=req, garage_id=1, user_id=1)

    async def test_refund_payment_not_found_raises(self, db_session: AsyncSession) -> None:
        req = RefundCreateRequest(payment_id=99999, amount_minor=1000)
        with pytest.raises(RefundNotFoundError):
            await cn_svc.record_refund(db_session, request=req, garage_id=1, user_id=1)

    async def test_get_refund_not_found_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(RefundNotFoundError):
            await cn_svc.get_refund(db_session, 99999, 1)

    async def test_refund_posts_balance_event(self, db_session: AsyncSession) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        inv, pmt = await _make_paid_invoice(db_session, customer.id, total=10000)
        # Pre-set outstanding (would be 0 after payment, but set for ledger clarity)
        customer.outstanding_minor = 0
        await db_session.flush()

        req = RefundCreateRequest(payment_id=pmt.id, amount_minor=4000)
        await cn_svc.record_refund(db_session, request=req, garage_id=1, user_id=1)

        events = (await db_session.execute(
            select(CustomerBalanceEvent)
            .where(
                CustomerBalanceEvent.customer_id == customer.id,
                CustomerBalanceEvent.reason == "refund_issued",
            )
        )).scalars().all()
        assert len(events) == 1
        assert events[0].delta_minor == 4000
