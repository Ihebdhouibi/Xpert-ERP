"""Tests for the payment module (#31)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

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
from app.modules.invoice.models import Invoice, InvoiceStatus
from app.modules.payment.models import Payment, PaymentMethod
from app.modules.payment import service as pay_svc
from app.modules.payment.service import InvoiceNotPayableError, OverpaymentError, PaymentError
from app.modules.payment.schemas import PaymentCreateRequest

# ---------------------------------------------------------------------------
# Permissions needed
# ---------------------------------------------------------------------------

PERMISSIONS = ["invoice.pay", "invoice.read", "quotation.read"]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_pay_db(db_session: AsyncSession) -> AsyncSession:
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
        email="admin@test.com",
        full_name="Test Admin",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    return db_session


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    return redis


@pytest_asyncio.fixture
async def pay_client(
    seeded_pay_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_pay_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_issued_invoice(db: AsyncSession, customer_id: int) -> Invoice:
    """Create a minimal issued invoice with total=10000."""
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.issued,
        doc_number="INV-TEST-001",
        subtotal_minor=10000,
        discount_minor=0,
        vat_minor=0,
        total_minor=10000,
        paid_amount_minor=0,
        outstanding_minor=10000,
        issued_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    await db.flush()
    return inv


async def _make_customer(db: AsyncSession) -> Customer:
    c = Customer(
        garage_id=1,
        type=CustomerType.individual,
        full_name="Test Customer",
        status=CustomerStatus.active,
    )
    db.add(c)
    await db.flush()
    return c


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPaymentService:
    async def test_record_full_payment(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(
            invoice_id=invoice.id,
            amount_minor=10000,
            payment_method=PaymentMethod.cash,
        )
        result = await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        assert result.amount_minor == 10000
        assert result.invoice_id == invoice.id
        assert result.payment_method == PaymentMethod.cash

    async def test_record_full_payment_sets_invoice_paid(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=10000)
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        updated = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated is not None
        assert updated.status == InvoiceStatus.paid
        assert updated.paid_amount_minor == 10000
        assert updated.outstanding_minor == 0

    async def test_record_partial_payment_sets_partial_status(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=4000)
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        updated = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated is not None
        assert updated.status == InvoiceStatus.partial
        assert updated.paid_amount_minor == 4000
        assert updated.outstanding_minor == 6000

    async def test_two_partial_payments_totalling_full(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req1 = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=6000)
        await pay_svc.record_payment(db_session, request=req1, garage_id=1, user_id=1)

        # Reload outstanding from DB before second payment
        updated = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated is not None
        assert updated.outstanding_minor == 4000

        req2 = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=4000)
        await pay_svc.record_payment(db_session, request=req2, garage_id=1, user_id=1)

        final = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert final is not None
        assert final.status == InvoiceStatus.paid

    async def test_overpayment_raises(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=20000)
        with pytest.raises(OverpaymentError):
            await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

    async def test_payment_on_draft_raises(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = Invoice(
            garage_id=1,
            customer_id=customer.id,
            status=InvoiceStatus.draft,
            subtotal_minor=10000,
            total_minor=10000,
            paid_amount_minor=0,
            outstanding_minor=10000,
        )
        db_session.add(inv)
        await db_session.flush()

        req = PaymentCreateRequest(invoice_id=inv.id, amount_minor=5000)
        with pytest.raises(InvoiceNotPayableError):
            await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

    async def test_payment_on_cancelled_raises(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        inv = Invoice(
            garage_id=1,
            customer_id=customer.id,
            status=InvoiceStatus.cancelled,
            subtotal_minor=10000,
            total_minor=10000,
            paid_amount_minor=0,
            outstanding_minor=10000,
        )
        db_session.add(inv)
        await db_session.flush()

        req = PaymentCreateRequest(invoice_id=inv.id, amount_minor=5000)
        with pytest.raises(InvoiceNotPayableError):
            await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

    async def test_payment_invoice_not_found_raises(self, db_session: AsyncSession) -> None:
        req = PaymentCreateRequest(invoice_id=9999, amount_minor=100)
        with pytest.raises(PaymentError):
            await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

    async def test_list_payments_returns_empty_initially(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        result = await pay_svc.list_payments(db_session, invoice_id=invoice.id, garage_id=1)
        assert list(result) == []

    async def test_list_payments_returns_recorded_payments(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=3000)
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        payments = await pay_svc.list_payments(db_session, invoice_id=invoice.id, garage_id=1)
        assert len(list(payments)) == 1

    async def test_list_payments_invoice_not_found_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(PaymentError):
            await pay_svc.list_payments(db_session, invoice_id=9999, garage_id=1)

    async def test_payment_method_stored_correctly(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(
            invoice_id=invoice.id,
            amount_minor=5000,
            payment_method=PaymentMethod.bank_transfer,
        )
        result = await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)
        assert result.payment_method == PaymentMethod.bank_transfer

    async def test_payment_reference_stored(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(
            invoice_id=invoice.id,
            amount_minor=10000,
            reference="BANK-REF-12345",
        )
        result = await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)
        assert result.reference == "BANK-REF-12345"

    async def test_custom_paid_at_stored(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        paid_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        req = PaymentCreateRequest(
            invoice_id=invoice.id,
            amount_minor=10000,
            paid_at=paid_at,
        )
        result = await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)
        assert result.paid_at.year == 2025
        assert result.paid_at.month == 1


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPaymentEndpoints:
    async def _login(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    async def test_record_payment_unauthenticated_returns_401(
        self, pay_client: AsyncClient
    ) -> None:
        resp = await pay_client.post(
            "/api/v1/payments",
            json={"invoice_id": 1, "amount_minor": 5000},
        )
        assert resp.status_code == 401

    async def test_list_payments_unauthenticated_returns_401(
        self, pay_client: AsyncClient
    ) -> None:
        resp = await pay_client.get("/api/v1/payments/invoices/1")
        assert resp.status_code == 401

    async def test_record_payment_invoice_not_found_returns_404(
        self, pay_client: AsyncClient
    ) -> None:
        token = await self._login(pay_client)
        with patch.object(
            pay_svc,
            "record_payment",
            new_callable=AsyncMock,
            side_effect=PaymentError("Invoice 999 not found."),
        ):
            resp = await pay_client.post(
                "/api/v1/payments",
                json={"invoice_id": 999, "amount_minor": 5000},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404

    async def test_record_payment_not_payable_returns_409(
        self, pay_client: AsyncClient
    ) -> None:
        token = await self._login(pay_client)
        with patch.object(
            pay_svc,
            "record_payment",
            new_callable=AsyncMock,
            side_effect=InvoiceNotPayableError(1, "draft"),
        ):
            resp = await pay_client.post(
                "/api/v1/payments",
                json={"invoice_id": 1, "amount_minor": 5000},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 409

    async def test_record_payment_overpayment_returns_422(
        self, pay_client: AsyncClient
    ) -> None:
        token = await self._login(pay_client)
        with patch.object(
            pay_svc,
            "record_payment",
            new_callable=AsyncMock,
            side_effect=OverpaymentError(1, 99999, 5000),
        ):
            resp = await pay_client.post(
                "/api/v1/payments",
                json={"invoice_id": 1, "amount_minor": 99999},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 422

    async def test_record_payment_success_returns_201(
        self, pay_client: AsyncClient
    ) -> None:
        from app.modules.payment.schemas import PaymentOut

        token = await self._login(pay_client)
        fake_out = PaymentOut(
            id=1,
            invoice_id=1,
            garage_id=1,
            amount_minor=5000,
            payment_method=PaymentMethod.cash,
            paid_at=datetime.now(timezone.utc),
            reference=None,
            notes=None,
            created_by=1,
            created_at=datetime.now(timezone.utc),
        )
        with patch.object(
            pay_svc,
            "record_payment",
            new_callable=AsyncMock,
            return_value=fake_out,
        ):
            resp = await pay_client.post(
                "/api/v1/payments",
                json={"invoice_id": 1, "amount_minor": 5000},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 201
        assert resp.json()["amount_minor"] == 5000

    async def test_list_payments_success_returns_200(
        self, pay_client: AsyncClient
    ) -> None:
        token = await self._login(pay_client)
        with patch.object(
            pay_svc,
            "list_payments",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await pay_client.get(
                "/api/v1/payments/invoices/1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_payments_invoice_not_found_returns_404(
        self, pay_client: AsyncClient
    ) -> None:
        token = await self._login(pay_client)
        with patch.object(
            pay_svc,
            "list_payments",
            new_callable=AsyncMock,
            side_effect=PaymentError("Invoice 999 not found."),
        ):
            resp = await pay_client.get(
                "/api/v1/payments/invoices/999",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
