"""Tests for the quotation module (#28) — VAT + discount calculations, CRUD, state machine."""
from __future__ import annotations

import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/xpert_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY_ID", "testkey")
os.environ.setdefault("S3_SECRET_ACCESS_KEY", "testsecret")
os.environ.setdefault("S3_BUCKET_DOCUMENTS", "test-documents")
os.environ.setdefault("S3_BUCKET_MEDIA", "test-media")

from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password
from app.modules.customer.models import Customer, CustomerStatus, CustomerType
from app.modules.quotation import service as quot_service
from app.modules.quotation.models import QuotationStatus
from app.modules.quotation.schemas import (
    QuotationCreateRequest,
    QuotationLineCreateRequest,
    QuotationUpdateRequest,
    QuotationLineUpdateRequest,
)
from app.modules.quotation.service import (
    QuotationNotFoundError,
    QuotationStateError,
    QuotationVersionError,
    _compute_line_total,
    _compute_line_vat,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

PERMISSIONS = [
    "quotation.read", "quotation.create", "quotation.update",
    "quotation.send", "quotation.approve_on_behalf",
]


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DB_URL, echo=False, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_quot_db(db_session: AsyncSession) -> AsyncSession:
    """Seed: permissions, admin role, user, and a test customer."""
    perms = [
        Permission(code=code, resource=code.split(".")[0], action=code.split(".")[-1], description="")
        for code in PERMISSIONS
    ]
    role = Role(code="admin", display_name="Administrator", is_system=True)
    db_session.add_all(perms + [role])
    await db_session.flush()

    for p in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=p.id))

    user = AppUser(
        garage_id=1, email="admin@test.com", full_name="Admin",
        password_hash=hash_password("Test1234!")
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))

    customer = Customer(
        garage_id=1, type=CustomerType.individual,
        full_name="Test Customer", status=CustomerStatus.active,
    )
    db_session.add(customer)
    await db_session.commit()
    return db_session


@pytest.fixture
def mock_redis() -> AsyncMock:
    r = AsyncMock()
    r.setex = AsyncMock(return_value=True)
    r.exists = AsyncMock(return_value=0)
    r.getdel = AsyncMock(return_value=None)
    return r


@pytest_asyncio.fixture
async def quot_client(seeded_quot_db: AsyncSession, mock_redis: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_db():
        yield seeded_quot_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, email="admin@test.com", password="Test1234!") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _get_customer_id(db: AsyncSession) -> int:
    from sqlalchemy import select
    from app.modules.customer.models import Customer
    result = await db.execute(select(Customer).limit(1))
    return result.scalar_one().id


# ---------------------------------------------------------------------------
# Unit: money calculation helpers
# ---------------------------------------------------------------------------

class TestMoneyCalculations:

    def test_line_total_no_discount(self):
        # 100.00 EUR * 2 qty, 0% discount = 200.00
        result = _compute_line_total(10000, Decimal("2"), Decimal("0"))
        assert result == 20000

    def test_line_total_with_10_percent_discount(self):
        # 100.00 EUR * 1, 10% discount = 90.00
        result = _compute_line_total(10000, Decimal("1"), Decimal("10"))
        assert result == 9000

    def test_line_total_with_20_percent_discount(self):
        # 100.00 EUR * 3, 20% discount = 240.00
        result = _compute_line_total(10000, Decimal("3"), Decimal("20"))
        assert result == 24000

    def test_line_total_100_percent_discount(self):
        result = _compute_line_total(10000, Decimal("1"), Decimal("100"))
        assert result == 0

    def test_line_total_fractional_quantity(self):
        # 100.00 * 0.5 = 50.00, no discount
        result = _compute_line_total(10000, Decimal("0.5"), Decimal("0"))
        assert result == 5000

    def test_line_vat_20_percent(self):
        # 100.00 * 20% = 20.00
        result = _compute_line_vat(10000, Decimal("20"))
        assert result == 2000

    def test_line_vat_zero(self):
        result = _compute_line_vat(10000, Decimal("0"))
        assert result == 0

    def test_line_vat_fractional(self):
        # 9999 * 20% = 1999.8 → rounds to 2000
        result = _compute_line_vat(9999, Decimal("20"))
        assert result == 2000

    def test_line_vat_rounds_half_up(self):
        # 100.05 * 10% = 10.005 → rounds to 10
        result = _compute_line_vat(10005, Decimal("10"))
        assert result == 1001  # 10005 * 0.10 = 1000.5 → 1001 (ROUND_HALF_UP)

    def test_discount_minor_is_gross_minus_subtotal(self):
        # gross = 10000*2 = 20000; discount 25% → subtotal = 15000; discount_minor = 5000
        assert _compute_line_total(10000, Decimal("2"), Decimal("25")) == 15000


# ---------------------------------------------------------------------------
# Service unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestQuotationService:

    async def test_create_empty_quotation(self, db_session: AsyncSession):
        # Need a customer first
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="John", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        assert out.status == QuotationStatus.draft
        assert out.version == 1
        assert out.subtotal_minor == 0
        assert out.total_minor == 0
        assert out.lines == []

    async def test_create_quotation_with_lines_calculates_totals(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="Jane", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        lines = [
            QuotationLineCreateRequest(
                description="Oil change",
                quantity=Decimal("1"),
                unit_price_minor=5000,     # 50.00
                discount_percent=Decimal("0"),
                vat_rate=Decimal("20"),
            ),
            QuotationLineCreateRequest(
                description="Filter",
                quantity=Decimal("2"),
                unit_price_minor=2000,     # 20.00 each → 40.00
                discount_percent=Decimal("10"),  # -10% → 36.00
                vat_rate=Decimal("20"),
            ),
        ]
        req = QuotationCreateRequest(customer_id=customer.id, lines=lines)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        # Line 1: 5000*1*(1-0) = 5000; VAT = 5000*0.2 = 1000
        # Line 2: 2000*2*(1-0.1) = 3600; VAT = 3600*0.2 = 720
        assert out.subtotal_minor == 8600        # 5000+3600
        assert out.discount_minor == 400         # 4000 gross - 3600 = 400
        assert out.vat_minor == 1720             # 1000+720
        assert out.total_minor == 10320          # 8600+1720
        assert len(out.lines) == 2

    async def test_get_nonexistent_raises(self, db_session: AsyncSession):
        with pytest.raises(QuotationNotFoundError):
            await quot_service.get_quotation(db_session, 9999, garage_id=1)

    async def test_quotation_isolated_by_garage(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="A", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        with pytest.raises(QuotationNotFoundError):
            await quot_service.get_quotation(db_session, out.id, garage_id=2)

    async def test_update_draft_quotation(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="B", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id, notes="initial")
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        updated = await quot_service.update_quotation(
            db_session, out.id, 1,
            request=QuotationUpdateRequest(notes="updated"),
            expected_version=1, user_id=1,
        )
        assert updated.notes == "updated"
        assert updated.version == 2

    async def test_update_version_mismatch_raises(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="C", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        with pytest.raises(QuotationVersionError):
            await quot_service.update_quotation(
                db_session, out.id, 1,
                request=QuotationUpdateRequest(notes="oops"),
                expected_version=99, user_id=1,
            )

    async def test_add_line_updates_totals(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="D", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        line_req = QuotationLineCreateRequest(
            description="Brake pads",
            quantity=Decimal("1"),
            unit_price_minor=8000,
            discount_percent=Decimal("0"),
            vat_rate=Decimal("20"),
        )
        updated = await quot_service.add_line(
            db_session, out.id, 1, request=line_req, expected_version=1, user_id=1
        )
        assert updated.subtotal_minor == 8000
        assert updated.vat_minor == 1600
        assert updated.total_minor == 9600
        assert len(updated.lines) == 1

    async def test_remove_line_updates_totals(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="E", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        lines = [
            QuotationLineCreateRequest(
                description="Item A", quantity=Decimal("1"),
                unit_price_minor=5000, discount_percent=Decimal("0"), vat_rate=Decimal("20")
            ),
            QuotationLineCreateRequest(
                description="Item B", quantity=Decimal("1"),
                unit_price_minor=3000, discount_percent=Decimal("0"), vat_rate=Decimal("20")
            ),
        ]
        req = QuotationCreateRequest(customer_id=customer.id, lines=lines)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        line_id = out.lines[0].id
        updated = await quot_service.remove_line(
            db_session, out.id, line_id, 1, expected_version=out.version, user_id=1
        )
        assert len(updated.lines) == 1
        assert updated.subtotal_minor == 3000

    async def test_send_assigns_doc_number(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="F", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        sent = await quot_service.send_quotation(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        assert sent.status == QuotationStatus.sent
        assert sent.doc_number is not None
        assert "QUOT" in sent.doc_number

    async def test_send_twice_raises_state_error(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="G", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        sent = await quot_service.send_quotation(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        with pytest.raises(QuotationStateError):
            await quot_service.send_quotation(
                db_session, out.id, 1, expected_version=sent.version, user_id=1
            )

    async def test_approve_from_sent(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="H", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        sent = await quot_service.send_quotation(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        approved = await quot_service.approve_quotation(
            db_session, out.id, 1, expected_version=sent.version, user_id=1
        )
        assert approved.status == QuotationStatus.approved

    async def test_reject_from_sent(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="I", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        sent = await quot_service.send_quotation(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        rejected = await quot_service.reject_quotation(
            db_session, out.id, 1, expected_version=sent.version, user_id=1
        )
        assert rejected.status == QuotationStatus.rejected

    async def test_cannot_approve_draft(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="J", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)

        with pytest.raises(QuotationStateError):
            await quot_service.approve_quotation(
                db_session, out.id, 1, expected_version=out.version, user_id=1
            )

    async def test_delete_draft_works(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="K", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        await quot_service.delete_quotation(db_session, out.id, 1, user_id=1)

        with pytest.raises(QuotationNotFoundError):
            await quot_service.get_quotation(db_session, out.id, 1)

    async def test_cannot_delete_sent_quotation(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="L", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        req = QuotationCreateRequest(customer_id=customer.id)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        sent = await quot_service.send_quotation(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        with pytest.raises(QuotationStateError):
            await quot_service.delete_quotation(db_session, out.id, 1, user_id=1)

    async def test_multiple_quotations_same_garage_sequential_doc_numbers(
        self, db_session: AsyncSession
    ):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="M", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        doc_numbers = []
        for _ in range(3):
            req = QuotationCreateRequest(customer_id=customer.id)
            out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
            sent = await quot_service.send_quotation(
                db_session, out.id, 1, expected_version=out.version, user_id=1
            )
            doc_numbers.append(sent.doc_number)

        # All distinct, all contain QUOT
        assert len(set(doc_numbers)) == 3
        assert all("QUOT" in d for d in doc_numbers)

    async def test_update_line_recalculates_totals(self, db_session: AsyncSession):
        customer = Customer(
            garage_id=1, type=CustomerType.individual,
            full_name="N", status=CustomerStatus.active,
        )
        db_session.add(customer)
        await db_session.flush()

        lines = [
            QuotationLineCreateRequest(
                description="X", quantity=Decimal("1"),
                unit_price_minor=5000, discount_percent=Decimal("0"), vat_rate=Decimal("0")
            )
        ]
        req = QuotationCreateRequest(customer_id=customer.id, lines=lines)
        out = await quot_service.create_quotation(db_session, request=req, garage_id=1, user_id=1)
        assert out.total_minor == 5000

        updated = await quot_service.update_line(
            db_session, out.id, out.lines[0].id, 1,
            request=QuotationLineUpdateRequest(unit_price_minor=8000),
            expected_version=out.version, user_id=1,
        )
        assert updated.total_minor == 8000


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestQuotationEndpoints:

    async def _create_quot(self, client: AsyncClient, token: str, customer_id: int) -> dict:
        resp = await client.post(
            "/api/v1/quotations",
            headers={"Authorization": f"Bearer {token}"},
            json={"customer_id": customer_id},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_create_quotation_201(self, quot_client: AsyncClient, seeded_quot_db: AsyncSession):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        data = await self._create_quot(quot_client, token, cid)
        assert data["status"] == "draft"
        assert data["version"] == 1

    async def test_list_quotations_empty(self, quot_client: AsyncClient):
        token = await _login(quot_client)
        resp = await quot_client.get(
            "/api/v1/quotations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_get_quotation(self, quot_client: AsyncClient, seeded_quot_db: AsyncSession):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)
        resp = await quot_client.get(
            f"/api/v1/quotations/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_not_found(self, quot_client: AsyncClient):
        token = await _login(quot_client)
        resp = await quot_client.get(
            "/api/v1/quotations/9999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_update_quotation_with_if_match(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        resp = await quot_client.patch(
            f"/api/v1/quotations/{created['id']}",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
            json={"notes": "updated via HTTP"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "updated via HTTP"
        assert resp.json()["version"] == 2

    async def test_update_without_if_match_returns_428(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        resp = await quot_client.patch(
            f"/api/v1/quotations/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"notes": "no if-match"},
        )
        assert resp.status_code == 428

    async def test_delete_draft_204(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        resp = await quot_client.delete(
            f"/api/v1/quotations/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    async def test_add_line_via_http(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        resp = await quot_client.post(
            f"/api/v1/quotations/{created['id']}/lines",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
            json={
                "description": "Labour: 1h",
                "quantity": "1.000",
                "unit_price_minor": 7500,
                "discount_percent": "0.00",
                "vat_rate": "20.00",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["lines"]) == 1
        assert data["subtotal_minor"] == 7500
        assert data["vat_minor"] == 1500
        assert data["total_minor"] == 9000

    async def test_send_quotation_assigns_doc_number(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        resp = await quot_client.post(
            f"/api/v1/quotations/{created['id']}/send",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["doc_number"] is not None
        assert "QUOT" in data["doc_number"]

    async def test_approve_after_send(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        send_resp = await quot_client.post(
            f"/api/v1/quotations/{created['id']}/send",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
        )
        assert send_resp.status_code == 200
        sent = send_resp.json()

        approve_resp = await quot_client.post(
            f"/api/v1/quotations/{created['id']}/approve",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(sent["version"])},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"

    async def test_reject_after_send(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)
        created = await self._create_quot(quot_client, token, cid)

        send_resp = await quot_client.post(
            f"/api/v1/quotations/{created['id']}/send",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
        )
        sent = send_resp.json()

        reject_resp = await quot_client.post(
            f"/api/v1/quotations/{created['id']}/reject",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(sent["version"])},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"

    async def test_requires_auth(self, quot_client: AsyncClient):
        resp = await quot_client.get("/api/v1/quotations")
        assert resp.status_code == 401

    async def test_list_filter_by_status(
        self, quot_client: AsyncClient, seeded_quot_db: AsyncSession
    ):
        token = await _login(quot_client)
        cid = await _get_customer_id(seeded_quot_db)

        # Create 2 drafts, send 1
        q1 = await self._create_quot(quot_client, token, cid)
        q2 = await self._create_quot(quot_client, token, cid)
        await quot_client.post(
            f"/api/v1/quotations/{q1['id']}/send",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(q1["version"])},
        )

        resp = await quot_client.get(
            "/api/v1/quotations?status=sent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "sent"
