"""Tests for the cash session module (#33)."""
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
from app.modules.cash_session.models import CashSession, CashSessionStatus
from app.modules.cash_session import service as cs_svc
from app.modules.cash_session import repository as cs_repo
from app.modules.payment.models import Payment, PaymentMethod
from app.modules.payment import service as pay_svc
from app.modules.payment.schemas import PaymentCreateRequest

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

PERMISSIONS = ["cash.open", "cash.close", "cash.read", "invoice.pay", "invoice.read"]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_cs_db(db_session: AsyncSession) -> AsyncSession:
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
def mock_redis_cs() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    return redis


@pytest_asyncio.fixture
async def cs_client(
    seeded_cs_db: AsyncSession, mock_redis_cs: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_cs_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis_cs

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
class TestCashSessionService:
    async def test_open_session_creates_open_session(self, db_session: AsyncSession) -> None:
        result = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        assert result.id is not None
        assert result.status == CashSessionStatus.open
        assert result.garage_id == 1
        assert result.closed_at is None

    async def test_cannot_open_second_session(self, db_session: AsyncSession) -> None:
        await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        with pytest.raises(cs_svc.SessionAlreadyOpenError):
            await cs_svc.open_session(db_session, garage_id=1, user_id=1)

    async def test_different_garages_can_each_have_open_session(self, db_session: AsyncSession) -> None:
        s1 = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        s2 = await cs_svc.open_session(db_session, garage_id=2, user_id=1)
        assert s1.id != s2.id
        assert s1.status == CashSessionStatus.open
        assert s2.status == CashSessionStatus.open

    async def test_close_session_with_zero_difference_no_reason_required(
        self, db_session: AsyncSession
    ) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        # No cash payments → expected = 0
        closed = await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=0,
            closing_reason=None,
        )
        assert closed.status == CashSessionStatus.closed
        assert closed.difference == 0
        assert closed.expected_total_cash == 0
        assert closed.counted_total_cash == 0

    async def test_close_session_computes_expected_from_cash_payments(
        self, db_session: AsyncSession
    ) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        # Record a cash payment — it will auto-link to the open session
        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=5000, payment_method=PaymentMethod.cash)
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        closed = await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=5000,
            closing_reason=None,
        )
        assert closed.expected_total_cash == 5000
        assert closed.difference == 0

    async def test_close_session_nonzero_difference_without_reason_raises(
        self, db_session: AsyncSession
    ) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        with pytest.raises(cs_svc.ClosingReasonRequiredError):
            await cs_svc.close_session(
                db_session,
                session_id=opened.id,
                garage_id=1,
                user_id=1,
                counted_total_cash=500,  # nonzero diff (expected=0)
                closing_reason=None,
            )

    async def test_close_session_nonzero_difference_with_reason_succeeds(
        self, db_session: AsyncSession
    ) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        closed = await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=500,
            closing_reason="Erreur de monnaie rendue",
        )
        assert closed.difference == 500
        assert closed.closing_reason == "Erreur de monnaie rendue"

    async def test_cannot_close_already_closed_session(self, db_session: AsyncSession) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=0,
        )
        with pytest.raises(cs_svc.SessionAlreadyClosedError):
            await cs_svc.close_session(
                db_session,
                session_id=opened.id,
                garage_id=1,
                user_id=1,
                counted_total_cash=0,
            )

    async def test_close_session_not_found_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(cs_svc.SessionNotFoundError):
            await cs_svc.close_session(
                db_session,
                session_id=99999,
                garage_id=1,
                user_id=1,
                counted_total_cash=0,
            )

    async def test_payment_auto_linked_to_open_session(self, db_session: AsyncSession) -> None:
        from app.modules.payment import repository as pay_repo

        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=3000)
        result = await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        assert result.cash_session_id == opened.id

    async def test_payment_without_open_session_has_no_session(self, db_session: AsyncSession) -> None:
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        req = PaymentCreateRequest(invoice_id=invoice.id, amount_minor=3000)
        result = await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        assert result.cash_session_id is None

    async def test_non_cash_payment_not_counted_in_expected_cash(
        self, db_session: AsyncSession
    ) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        customer = await _make_customer(db_session)
        invoice = await _make_issued_invoice(db_session, customer.id)

        # Card payment — should NOT count in expected cash
        req = PaymentCreateRequest(
            invoice_id=invoice.id, amount_minor=5000, payment_method=PaymentMethod.card
        )
        await pay_svc.record_payment(db_session, request=req, garage_id=1, user_id=1)

        closed = await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=0,
        )
        # Card payment not counted → expected cash = 0, diff = 0
        assert closed.expected_total_cash == 0
        assert closed.difference == 0

    async def test_z_report_data_totals(self, db_session: AsyncSession) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        customer = await _make_customer(db_session)
        inv1 = await _make_issued_invoice(db_session, customer.id, total=10000)
        inv2 = await _make_issued_invoice(db_session, customer.id, total=10000)

        await pay_svc.record_payment(
            db_session,
            request=PaymentCreateRequest(invoice_id=inv1.id, amount_minor=3000, payment_method=PaymentMethod.cash),
            garage_id=1, user_id=1,
        )
        await pay_svc.record_payment(
            db_session,
            request=PaymentCreateRequest(invoice_id=inv2.id, amount_minor=2000, payment_method=PaymentMethod.card),
            garage_id=1, user_id=1,
        )

        await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=3000,
        )

        report = await cs_svc.get_z_report_data(db_session, opened.id, 1)
        assert report.total_all_methods == 5000
        method_totals = {t.payment_method: t.total_minor for t in report.tallies}
        assert method_totals[PaymentMethod.cash] == 3000
        assert method_totals[PaymentMethod.card] == 2000

    async def test_list_sessions_empty(self, db_session: AsyncSession) -> None:
        result = await cs_svc.list_sessions(db_session, garage_id=1)
        assert result.total == 0

    async def test_list_sessions_after_open(self, db_session: AsyncSession) -> None:
        await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        result = await cs_svc.list_sessions(db_session, garage_id=1)
        assert result.total == 1

    async def test_get_current_open_session_none_when_closed(self, db_session: AsyncSession) -> None:
        opened = await cs_svc.open_session(db_session, garage_id=1, user_id=1)
        await cs_svc.close_session(
            db_session,
            session_id=opened.id,
            garage_id=1,
            user_id=1,
            counted_total_cash=0,
        )
        current = await cs_svc.get_current_open_session(db_session, 1)
        assert current is None


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCashSessionEndpoints:
    async def _login(self, client: AsyncClient) -> str:
        resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "Test1234!",
        })
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    async def test_open_session_unauthenticated(self, cs_client: AsyncClient) -> None:
        resp = await cs_client.post("/api/v1/cash-sessions")
        assert resp.status_code == 401

    async def test_open_session_success(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        resp = await cs_client.post(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "open"
        assert data["closed_at"] is None

    async def test_open_second_session_returns_409(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        await cs_client.post(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await cs_client.post(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    async def test_close_session_success(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        open_resp = await cs_client.post(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = open_resp.json()["id"]

        resp = await cs_client.post(
            f"/api/v1/cash-sessions/{session_id}/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"counted_total_cash": 0},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "closed"
        assert data["difference"] == 0

    async def test_close_nonzero_diff_without_reason_returns_422(
        self, cs_client: AsyncClient
    ) -> None:
        token = await self._login(cs_client)
        open_resp = await cs_client.post(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = open_resp.json()["id"]

        resp = await cs_client.post(
            f"/api/v1/cash-sessions/{session_id}/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"counted_total_cash": 1000},
        )
        assert resp.status_code == 422

    async def test_close_session_not_found_returns_404(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        resp = await cs_client.post(
            "/api/v1/cash-sessions/99999/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"counted_total_cash": 0},
        )
        assert resp.status_code == 404

    async def test_get_current_session_none(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        resp = await cs_client.get(
            "/api/v1/cash-sessions/current",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_list_sessions_empty(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        resp = await cs_client.get(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_get_z_report_after_close(self, cs_client: AsyncClient) -> None:
        token = await self._login(cs_client)
        open_resp = await cs_client.post(
            "/api/v1/cash-sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = open_resp.json()["id"]
        await cs_client.post(
            f"/api/v1/cash-sessions/{session_id}/close",
            headers={"Authorization": f"Bearer {token}"},
            json={"counted_total_cash": 0},
        )
        resp = await cs_client.get(
            f"/api/v1/cash-sessions/{session_id}/z-report",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["total_all_methods"] == 0
