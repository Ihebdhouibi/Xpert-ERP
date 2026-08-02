"""Tests for the advance payment module (#32)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock

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
from app.modules.advance_payment.models import AdvancePayment
from app.modules.advance_payment import service as adv_svc
from app.modules.advance_payment import repository as adv_repo
from app.modules.advance_payment.schemas import AdvancePaymentCreateRequest
from app.modules.payment.models import PaymentMethod

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

PERMISSIONS = ["deposit.record", "invoice.read"]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_adv_db(db_session: AsyncSession) -> AsyncSession:
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
def mock_redis_adv() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
async def adv_client(
    seeded_adv_db: AsyncSession, mock_redis_adv: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_adv_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis_adv

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_customer(db: AsyncSession, garage_id: int = 1) -> Customer:
    c = Customer(
        garage_id=garage_id,
        type=CustomerType.individual,
        full_name="Test Customer",
        status=CustomerStatus.active,
    )
    db.add(c)
    await db.flush()
    return c


async def _make_draft_invoice(db: AsyncSession, customer_id: int, total: int = 10000) -> Invoice:
    """Create a minimal draft invoice."""
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
    )
    db.add(inv)
    await db.flush()
    return inv


async def _make_issued_invoice(db: AsyncSession, customer_id: int, total: int = 10000) -> Invoice:
    inv = Invoice(
        garage_id=1,
        customer_id=customer_id,
        status=InvoiceStatus.issued,
        doc_number="INV-TEST-001",
        subtotal_minor=total,
        discount_minor=0,
        vat_minor=0,
        total_minor=total,
        paid_amount_minor=0,
        outstanding_minor=total,
        issued_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    await db.flush()
    return inv


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdvancePaymentService:
    async def test_record_advance_creates_unapplied(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        req = AdvancePaymentCreateRequest(
            customer_id=customer.id,
            amount_minor=5000,
            payment_method=PaymentMethod.cash,
        )
        result = await adv_svc.record_advance(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert result.id is not None
        assert result.amount_minor == 5000
        assert result.applied_to_invoice_id is None
        assert result.applied_at is None

    async def test_record_advance_customer_not_found(self, db_session: AsyncSession) -> None:
        req = AdvancePaymentCreateRequest(
            customer_id=99999,
            amount_minor=5000,
        )
        with pytest.raises(adv_svc.CustomerNotFoundError):
            await adv_svc.record_advance(
                db_session, request=req, garage_id=1, user_id=1
            )

    async def test_record_advance_stores_payment_method(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        req = AdvancePaymentCreateRequest(
            customer_id=customer.id,
            amount_minor=3000,
            payment_method=PaymentMethod.card,
        )
        result = await adv_svc.record_advance(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert result.payment_method == PaymentMethod.card

    async def test_record_advance_stores_reference(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        req = AdvancePaymentCreateRequest(
            customer_id=customer.id,
            amount_minor=3000,
            reference="DEP-001",
        )
        result = await adv_svc.record_advance(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert result.reference == "DEP-001"

    async def test_record_advance_stores_repair_order_id(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        req = AdvancePaymentCreateRequest(
            customer_id=customer.id,
            amount_minor=2000,
            repair_order_id=42,
        )
        result = await adv_svc.record_advance(
            db_session, request=req, garage_id=1, user_id=1
        )
        assert result.repair_order_id == 42

    async def test_apply_advances_deducts_outstanding(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        # Record advance before invoice
        advance = AdvancePayment(
            garage_id=1,
            customer_id=customer.id,
            amount_minor=3000,
            payment_method=PaymentMethod.cash,
            paid_at=datetime.now(timezone.utc),
        )
        db_session.add(advance)
        await db_session.flush()

        invoice = await _make_issued_invoice(db_session, customer.id, total=10000)

        applied = await adv_svc.apply_advances_to_invoice(
            db_session,
            invoice_id=invoice.id,
            customer_id=customer.id,
            garage_id=1,
        )
        await db_session.commit()

        assert applied == 3000
        updated_inv = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated_inv is not None
        assert updated_inv.outstanding_minor == 7000
        assert updated_inv.paid_amount_minor == 3000
        assert updated_inv.status == InvoiceStatus.partial

    async def test_apply_advances_full_coverage_sets_paid(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        advance = AdvancePayment(
            garage_id=1,
            customer_id=customer.id,
            amount_minor=10000,
            payment_method=PaymentMethod.cash,
            paid_at=datetime.now(timezone.utc),
        )
        db_session.add(advance)
        await db_session.flush()

        invoice = await _make_issued_invoice(db_session, customer.id, total=10000)

        applied = await adv_svc.apply_advances_to_invoice(
            db_session,
            invoice_id=invoice.id,
            customer_id=customer.id,
            garage_id=1,
        )
        await db_session.commit()

        assert applied == 10000
        updated_inv = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated_inv is not None
        assert updated_inv.outstanding_minor == 0
        assert updated_inv.status == InvoiceStatus.paid

    async def test_apply_advances_marks_advance_as_applied(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        advance = AdvancePayment(
            garage_id=1,
            customer_id=customer.id,
            amount_minor=5000,
            payment_method=PaymentMethod.cash,
            paid_at=datetime.now(timezone.utc),
        )
        db_session.add(advance)
        await db_session.flush()
        advance_id = advance.id

        invoice = await _make_issued_invoice(db_session, customer.id, total=10000)

        await adv_svc.apply_advances_to_invoice(
            db_session,
            invoice_id=invoice.id,
            customer_id=customer.id,
            garage_id=1,
        )
        await db_session.commit()

        updated_adv = await adv_repo.get_by_id(db_session, advance_id, 1)
        assert updated_adv is not None
        assert updated_adv.applied_to_invoice_id == invoice.id
        assert updated_adv.applied_at is not None

    async def test_apply_advances_multiple_fifo(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        # Two advances: 3000 + 4000 = 7000; invoice total = 5000
        advances_created = []
        for amount in (3000, 4000):
            adv = AdvancePayment(
                garage_id=1,
                customer_id=customer.id,
                amount_minor=amount,
                payment_method=PaymentMethod.cash,
                paid_at=datetime.now(timezone.utc),
            )
            db_session.add(adv)
            advances_created.append(adv)
        await db_session.flush()
        adv1_id, adv2_id = advances_created[0].id, advances_created[1].id

        invoice = await _make_issued_invoice(db_session, customer.id, total=5000)

        applied = await adv_svc.apply_advances_to_invoice(
            db_session,
            invoice_id=invoice.id,
            customer_id=customer.id,
            garage_id=1,
        )
        await db_session.commit()

        # First advance (3000) fully applied, second (4000) partially applied (2000 used)
        assert applied == 5000
        updated_inv = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated_inv is not None
        assert updated_inv.outstanding_minor == 0
        assert updated_inv.status == InvoiceStatus.paid

        # First advance: applied in full
        adv1 = await adv_repo.get_by_id(db_session, adv1_id, 1)
        assert adv1 is not None
        assert adv1.applied_amount_minor == 3000

        # Second advance: only 2000 of 4000 applied
        adv2 = await adv_repo.get_by_id(db_session, adv2_id, 1)
        assert adv2 is not None
        assert adv2.applied_amount_minor == 2000

    async def test_apply_advances_no_advances_is_noop(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id, total=10000)

        applied = await adv_svc.apply_advances_to_invoice(
            db_session,
            invoice_id=invoice.id,
            customer_id=customer.id,
            garage_id=1,
        )
        await db_session.commit()

        assert applied == 0
        updated_inv = await inv_repo.get_by_id(db_session, invoice.id, 1)
        assert updated_inv is not None
        assert updated_inv.outstanding_minor == 10000
        assert updated_inv.status == InvoiceStatus.issued

    async def test_apply_advances_already_applied_not_reused(self, db_session: AsyncSession) -> None:
        from app.modules.invoice import repository as inv_repo

        customer = await _make_customer(db_session)
        invoice1 = await _make_issued_invoice(db_session, customer.id, total=10000)

        # Create advance and mark already applied to invoice1
        advance = AdvancePayment(
            garage_id=1,
            customer_id=customer.id,
            amount_minor=5000,
            payment_method=PaymentMethod.cash,
            paid_at=datetime.now(timezone.utc),
            applied_to_invoice_id=invoice1.id,
            applied_at=datetime.now(timezone.utc),
        )
        db_session.add(advance)
        await db_session.flush()

        # Second invoice — advance should NOT be reused
        invoice2 = await _make_issued_invoice(db_session, customer.id, total=8000)
        applied = await adv_svc.apply_advances_to_invoice(
            db_session,
            invoice_id=invoice2.id,
            customer_id=customer.id,
            garage_id=1,
        )
        await db_session.commit()

        assert applied == 0
        inv2 = await inv_repo.get_by_id(db_session, invoice2.id, 1)
        assert inv2 is not None
        assert inv2.outstanding_minor == 8000

    async def test_list_advances_empty(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        result = await adv_svc.list_advances(
            db_session, customer_id=customer.id, garage_id=1
        )
        assert result.total == 0
        assert result.items == []

    async def test_list_advances_returns_all(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        for amount in (2000, 3000):
            req = AdvancePaymentCreateRequest(
                customer_id=customer.id, amount_minor=amount
            )
            await adv_svc.record_advance(
                db_session, request=req, garage_id=1, user_id=1
            )
        result = await adv_svc.list_advances(
            db_session, customer_id=customer.id, garage_id=1
        )
        assert result.total == 2
        amounts = {a.amount_minor for a in result.items}
        assert amounts == {2000, 3000}

    async def test_garage_isolation_advances(self, db_session: AsyncSession) -> None:
        customer1 = await _make_customer(db_session, garage_id=1)
        customer2 = await _make_customer(db_session, garage_id=2)

        adv = AdvancePayment(
            garage_id=2,
            customer_id=customer2.id,
            amount_minor=5000,
            payment_method=PaymentMethod.cash,
            paid_at=datetime.now(timezone.utc),
        )
        db_session.add(adv)
        await db_session.flush()

        # garage 1 should not see garage 2's advances
        unapplied = await adv_repo.list_unapplied_by_customer(
            db_session, customer_id=customer2.id, garage_id=1
        )
        assert unapplied == []


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdvancePaymentEndpoints:
    async def test_record_advance_unauthenticated(self, adv_client: AsyncClient) -> None:
        resp = await adv_client.post("/api/v1/advance-payments", json={
            "customer_id": 1, "amount_minor": 5000
        })
        assert resp.status_code == 401

    async def test_list_advances_unauthenticated(self, adv_client: AsyncClient) -> None:
        resp = await adv_client.get("/api/v1/advance-payments/customers/1")
        assert resp.status_code == 401

    async def _login(self, client: AsyncClient) -> str:
        resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "Test1234!",
        })
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    async def test_record_advance_customer_not_found(self, adv_client: AsyncClient) -> None:
        token = await self._login(adv_client)
        resp = await adv_client.post(
            "/api/v1/advance-payments",
            headers={"Authorization": f"Bearer {token}"},
            json={"customer_id": 99999, "amount_minor": 5000},
        )
        assert resp.status_code == 404

    async def test_record_advance_success(
        self, adv_client: AsyncClient, seeded_adv_db: AsyncSession
    ) -> None:
        # Create a customer
        customer = Customer(
            garage_id=1,
            type=CustomerType.individual,
            full_name="Deposit Customer",
            status=CustomerStatus.active,
        )
        seeded_adv_db.add(customer)
        await seeded_adv_db.commit()

        token = await self._login(adv_client)
        resp = await adv_client.post(
            "/api/v1/advance-payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "customer_id": customer.id,
                "amount_minor": 7500,
                "payment_method": "cash",
                "reference": "DEP-001",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["amount_minor"] == 7500
        assert data["applied_to_invoice_id"] is None
        assert data["reference"] == "DEP-001"

    async def test_list_advances_empty(
        self, adv_client: AsyncClient, seeded_adv_db: AsyncSession
    ) -> None:
        customer = Customer(
            garage_id=1,
            type=CustomerType.individual,
            full_name="Empty Customer",
            status=CustomerStatus.active,
        )
        seeded_adv_db.add(customer)
        await seeded_adv_db.commit()

        token = await self._login(adv_client)
        resp = await adv_client.get(
            f"/api/v1/advance-payments/customers/{customer.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_advances_shows_recorded(
        self, adv_client: AsyncClient, seeded_adv_db: AsyncSession
    ) -> None:
        customer = Customer(
            garage_id=1,
            type=CustomerType.individual,
            full_name="Advance Customer",
            status=CustomerStatus.active,
        )
        seeded_adv_db.add(customer)
        await seeded_adv_db.commit()

        token = await self._login(adv_client)
        # Record an advance
        await adv_client.post(
            "/api/v1/advance-payments",
            headers={"Authorization": f"Bearer {token}"},
            json={"customer_id": customer.id, "amount_minor": 4000},
        )
        resp = await adv_client.get(
            f"/api/v1/advance-payments/customers/{customer.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["amount_minor"] == 4000
