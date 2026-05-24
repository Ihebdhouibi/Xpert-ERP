"""Tests for customer credit limit enforcement and balance ledger (#34)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password
from app.modules.customer.models import Customer, CustomerStatus, CustomerType
from app.modules.customer.credit_service import (
    CreditLimitExceededError,
    check_credit_limit,
    post_balance_event,
    recompute_outstanding,
)
from app.modules.invoice.models import Invoice, InvoiceStatus
from app.modules.invoice import service as inv_svc
from app.modules.invoice.schemas import InvoiceCreateRequest, InvoiceLineCreateRequest
from app.modules.payment.models import PaymentMethod
from app.modules.payment import service as pay_svc
from app.modules.payment.schemas import PaymentCreateRequest

from unittest.mock import AsyncMock

# ---------------------------------------------------------------------------
# Permissions list
# ---------------------------------------------------------------------------
PERMISSIONS = [
    "invoice.create", "invoice.issue", "invoice.read", "invoice.pay",
    "invoice.cancel",
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_credit_db(db_session: AsyncSession) -> AsyncSession:
    perms = [
        Permission(
            code=code,
            resource=code.split(".")[0],
            action=code.split(".")[-1],
            description="",
        )
        for code in PERMISSIONS
    ]
    role = Role(code="admin", display_name="Admin", is_system=True)
    db_session.add_all([*perms, role])
    await db_session.flush()

    for perm in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = AppUser(
        garage_id=1,
        email="admin@credit.com",
        full_name="Credit Admin",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_customer(db: AsyncSession, credit_limit: int = 0) -> Customer:
    c = Customer(
        garage_id=1,
        type=CustomerType.individual,
        full_name="Credit Test Customer",
        status=CustomerStatus.active,
        credit_limit_minor=credit_limit,
    )
    db.add(c)
    await db.flush()
    return c


async def _make_draft_invoice(db: AsyncSession, customer_id: int, total: int = 10000) -> Invoice:
    """Create a bare draft invoice (bypassing service, for speed)."""
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


async def _make_issued_invoice(db: AsyncSession, customer_id: int, total: int = 10000) -> Invoice:
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.issued,
        doc_number="INV-CREDIT-001",
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


# ---------------------------------------------------------------------------
# Balance ledger tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBalanceLedger:
    async def test_post_event_increases_outstanding(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        await post_balance_event(
            db_session,
            customer_id=customer.id,
            garage_id=1,
            reason="invoice_issued",
            delta_minor=5000,
            currency="EUR",
            ref_type="invoice",
            ref_id=1,
        )
        await db_session.flush()
        assert customer.outstanding_minor == 5000

    async def test_post_credit_event_decreases_outstanding(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        await post_balance_event(
            db_session, customer_id=customer.id, garage_id=1,
            reason="invoice_issued", delta_minor=8000, currency="EUR",
        )
        await post_balance_event(
            db_session, customer_id=customer.id, garage_id=1,
            reason="payment_received", delta_minor=-3000, currency="EUR",
        )
        await db_session.flush()
        assert customer.outstanding_minor == 5000

    async def test_post_multiple_events_accumulate(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        for amount in [2000, 3000, 4000]:
            await post_balance_event(
                db_session, customer_id=customer.id, garage_id=1,
                reason="invoice_issued", delta_minor=amount, currency="EUR",
            )
        await db_session.flush()
        assert customer.outstanding_minor == 9000

    async def test_recompute_outstanding_matches_sum(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        await post_balance_event(
            db_session, customer_id=customer.id, garage_id=1,
            reason="invoice_issued", delta_minor=6000, currency="EUR",
        )
        await post_balance_event(
            db_session, customer_id=customer.id, garage_id=1,
            reason="payment_received", delta_minor=-2000, currency="EUR",
        )
        await db_session.commit()

        # Manually corrupt the snapshot
        customer.outstanding_minor = 0
        await db_session.flush()

        total = await recompute_outstanding(db_session, customer_id=customer.id, garage_id=1)
        assert total == 4000
        assert customer.outstanding_minor == 4000

    async def test_event_ref_type_and_ref_id_stored(self, db_session: AsyncSession) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        event = await post_balance_event(
            db_session, customer_id=customer.id, garage_id=1,
            reason="invoice_issued", delta_minor=1000, currency="EUR",
            ref_type="invoice", ref_id=42,
        )
        assert event.ref_type == "invoice"
        assert event.ref_id == 42

    async def test_event_created_by_stored(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        event = await post_balance_event(
            db_session, customer_id=customer.id, garage_id=1,
            reason="invoice_issued", delta_minor=1000, currency="EUR",
            created_by=7,
        )
        assert event.created_by_user_id == 7


# ---------------------------------------------------------------------------
# Credit limit enforcement tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreditLimitEnforcement:
    async def test_no_limit_always_passes(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session, credit_limit=0)
        # Should not raise
        await check_credit_limit(
            db_session, customer_id=customer.id, garage_id=1, additional_amount_minor=9_999_999
        )

    async def test_within_limit_passes(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session, credit_limit=10000)
        await check_credit_limit(
            db_session, customer_id=customer.id, garage_id=1, additional_amount_minor=9999
        )

    async def test_exactly_at_limit_passes(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session, credit_limit=10000)
        await check_credit_limit(
            db_session, customer_id=customer.id, garage_id=1, additional_amount_minor=10000
        )

    async def test_exceed_limit_block_mode_raises(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core import config as cfg_module
        monkeypatch.setattr(cfg_module.get_settings(), "credit_limit_mode", "block")

        customer = await _make_customer(db_session, credit_limit=10000)
        # Give customer existing outstanding
        customer.outstanding_minor = 8000
        await db_session.flush()

        with pytest.raises(CreditLimitExceededError) as exc_info:
            await check_credit_limit(
                db_session, customer_id=customer.id, garage_id=1,
                additional_amount_minor=5000,  # 8000 + 5000 = 13000 > 10000
            )
        assert exc_info.value.customer_id == customer.id

    async def test_exceed_limit_warn_mode_does_not_raise(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core import config as cfg_module
        monkeypatch.setattr(cfg_module.get_settings(), "credit_limit_mode", "warn")

        customer = await _make_customer(db_session, credit_limit=10000)
        customer.outstanding_minor = 8000
        await db_session.flush()

        # Should NOT raise
        await check_credit_limit(
            db_session, customer_id=customer.id, garage_id=1, additional_amount_minor=5000
        )

    async def test_unknown_customer_id_passes_silently(self, db_session: AsyncSession) -> None:
        # Non-existent customer — should not raise
        await check_credit_limit(
            db_session, customer_id=99999, garage_id=1, additional_amount_minor=99999
        )


# ---------------------------------------------------------------------------
# Integration tests — invoice issue posts to ledger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInvoiceIssueLedgerIntegration:
    async def test_issue_invoice_posts_debit_event(self, db_session: AsyncSession) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        inv = await _make_draft_invoice(db_session, customer.id, total=7500)

        await inv_svc.issue_invoice(
            db_session, inv.id, 1, expected_version=1, user_id=1
        )

        events = (await db_session.execute(
            select(CustomerBalanceEvent).where(CustomerBalanceEvent.customer_id == customer.id)
        )).scalars().all()
        assert len(events) == 1
        assert events[0].reason == "invoice_issued"
        assert events[0].delta_minor == 7500
        assert events[0].ref_type == "invoice"

    async def test_issue_invoice_updates_customer_outstanding(self, db_session: AsyncSession) -> None:
        from app.modules.customer import repository as cust_repo

        customer = await _make_customer(db_session)
        inv = await _make_draft_invoice(db_session, customer.id, total=6000)
        await inv_svc.issue_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        fresh_customer = await cust_repo.get_by_id(db_session, 1, customer.id)
        assert fresh_customer.outstanding_minor == 6000

    async def test_cancel_issued_invoice_reverses_balance(self, db_session: AsyncSession) -> None:
        from app.modules.customer import repository as cust_repo

        customer = await _make_customer(db_session)
        inv = await _make_draft_invoice(db_session, customer.id, total=5000)
        issued = await inv_svc.issue_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        # Version is now 2 after issue
        await inv_svc.cancel_invoice(
            db_session, inv.id, 1, expected_version=issued.version, user_id=1
        )

        fresh_customer = await cust_repo.get_by_id(db_session, 1, customer.id)
        assert fresh_customer.outstanding_minor == 0

    async def test_cancel_draft_invoice_no_balance_event(self, db_session: AsyncSession) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        inv = await _make_draft_invoice(db_session, customer.id, total=3000)
        # Cancel while still draft — no balance event should be posted
        await inv_svc.cancel_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

        events = (await db_session.execute(
            select(CustomerBalanceEvent).where(CustomerBalanceEvent.customer_id == customer.id)
        )).scalars().all()
        assert len(events) == 0

    async def test_issue_blocked_when_credit_limit_exceeded(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core import config as cfg_module
        monkeypatch.setattr(cfg_module.get_settings(), "credit_limit_mode", "block")

        customer = await _make_customer(db_session, credit_limit=5000)
        inv = await _make_draft_invoice(db_session, customer.id, total=6000)

        with pytest.raises(CreditLimitExceededError):
            await inv_svc.issue_invoice(db_session, inv.id, 1, expected_version=1, user_id=1)

    async def test_payment_posts_credit_event(self, db_session: AsyncSession) -> None:
        from app.modules.customer.models import CustomerBalanceEvent
        from sqlalchemy import select

        customer = await _make_customer(db_session)
        inv = await _make_issued_invoice(db_session, customer.id, total=10000)
        # Pre-set customer outstanding to match
        customer.outstanding_minor = 10000
        await db_session.flush()

        req = PaymentCreateRequest(
            invoice_id=inv.id, amount_minor=4000, payment_method=PaymentMethod.cash
        )
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        events = (await db_session.execute(
            select(CustomerBalanceEvent)
            .where(
                CustomerBalanceEvent.customer_id == customer.id,
                CustomerBalanceEvent.reason == "payment_received",
            )
        )).scalars().all()
        assert len(events) == 1
        assert events[0].delta_minor == -4000

    async def test_payment_reduces_customer_outstanding(self, db_session: AsyncSession) -> None:
        from app.modules.customer import repository as cust_repo

        customer = await _make_customer(db_session)
        customer.outstanding_minor = 10000
        inv = await _make_issued_invoice(db_session, customer.id, total=10000)
        await db_session.flush()

        req = PaymentCreateRequest(
            invoice_id=inv.id, amount_minor=6000, payment_method=PaymentMethod.cash
        )
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        fresh = await cust_repo.get_by_id(db_session, 1, customer.id)
        assert fresh.outstanding_minor == 4000
