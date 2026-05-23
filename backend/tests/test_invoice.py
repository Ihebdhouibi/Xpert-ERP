"""Tests for the invoice module (#29) — CRUD, conversion flows, state machine."""
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
from app.modules.invoice import service as inv_service
from app.modules.invoice.models import InvoiceStatus
from app.modules.invoice.schemas import (
    InvoiceCreateRequest,
    InvoiceLineCreateRequest,
    InvoiceUpdateRequest,
    InvoiceLineUpdateRequest,
)
from app.modules.invoice.service import (
    InvoiceNotFoundError,
    InvoiceStateError,
    InvoiceVersionError,
    QuotationAlreadyConvertedError,
)
from app.modules.quotation import service as quot_service
from app.modules.quotation.models import QuotationStatus
from app.modules.quotation.schemas import QuotationCreateRequest, QuotationLineCreateRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

PERMISSIONS = [
    "invoice.read", "invoice.create", "invoice.update",
    "invoice.issue", "invoice.cancel",
    "quotation.read", "quotation.create", "quotation.update",
    "quotation.send", "quotation.approve_on_behalf", "quotation.convert",
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
async def seeded_inv_db(db_session: AsyncSession) -> AsyncSession:
    perms = [
        Permission(code=c, resource=c.split(".")[0], action=c.split(".")[-1], description="")
        for c in PERMISSIONS
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
async def inv_client(
    seeded_inv_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    async def override_db():
        yield seeded_inv_db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _login(client: AsyncClient) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Test1234!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _customer_id(db: AsyncSession) -> int:
    from sqlalchemy import select
    result = await db.execute(select(Customer).limit(1))
    return result.scalar_one().id


def _line(price: int = 5000, qty: str = "1", vat: str = "20") -> InvoiceLineCreateRequest:
    return InvoiceLineCreateRequest(
        description="Test item",
        quantity=Decimal(qty),
        unit_price_minor=price,
        discount_percent=Decimal("0"),
        vat_rate=Decimal(vat),
    )


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------

class TestInvoiceService:

    async def test_create_empty_invoice(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="X", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        req = InvoiceCreateRequest(customer_id=customer.id)
        out = await inv_service.create_invoice(db_session, request=req, garage_id=1, user_id=1)
        assert out.status == InvoiceStatus.draft
        assert out.version == 1
        assert out.total_minor == 0
        assert out.outstanding_minor == 0

    async def test_create_invoice_with_lines_calculates_totals(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Y", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        lines = [
            InvoiceLineCreateRequest(
                description="Labour",
                quantity=Decimal("2"),
                unit_price_minor=5000,   # 100.00 gross
                discount_percent=Decimal("10"),  # 90.00 net
                vat_rate=Decimal("20"),   # VAT = 18.00
            )
        ]
        req = InvoiceCreateRequest(customer_id=customer.id, lines=lines)
        out = await inv_service.create_invoice(db_session, request=req, garage_id=1, user_id=1)
        assert out.subtotal_minor == 9000
        assert out.discount_minor == 1000
        assert out.vat_minor == 1800
        assert out.total_minor == 10800
        assert out.outstanding_minor == 10800
        assert out.paid_amount_minor == 0

    async def test_get_invoice_not_found(self, db_session: AsyncSession):
        with pytest.raises(InvoiceNotFoundError):
            await inv_service.get_invoice(db_session, 9999, garage_id=1)

    async def test_invoice_garage_isolation(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Z", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        req = InvoiceCreateRequest(customer_id=customer.id)
        out = await inv_service.create_invoice(db_session, request=req, garage_id=1, user_id=1)
        with pytest.raises(InvoiceNotFoundError):
            await inv_service.get_invoice(db_session, out.id, garage_id=2)

    async def test_update_draft_invoice(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="A", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        updated = await inv_service.update_invoice(
            db_session, out.id, 1,
            request=InvoiceUpdateRequest(notes="test note"),
            expected_version=1, user_id=1,
        )
        assert updated.notes == "test note"
        assert updated.version == 2

    async def test_update_version_mismatch(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="B", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        with pytest.raises(InvoiceVersionError):
            await inv_service.update_invoice(
                db_session, out.id, 1,
                request=InvoiceUpdateRequest(notes="oops"),
                expected_version=99, user_id=1,
            )

    async def test_issue_assigns_doc_number(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="C", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        issued = await inv_service.issue_invoice(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        assert issued.status == InvoiceStatus.issued
        assert issued.doc_number is not None
        assert "INV" in issued.doc_number
        assert issued.issued_at is not None

    async def test_cannot_issue_twice(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="D", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        issued = await inv_service.issue_invoice(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        with pytest.raises(InvoiceStateError):
            await inv_service.issue_invoice(
                db_session, issued.id, 1, expected_version=issued.version, user_id=1
            )

    async def test_cancel_draft(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="E", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        cancelled = await inv_service.cancel_invoice(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        assert cancelled.status == InvoiceStatus.cancelled

    async def test_cancel_issued(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="F", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        issued = await inv_service.issue_invoice(
            db_session, out.id, 1, expected_version=out.version, user_id=1
        )
        cancelled = await inv_service.cancel_invoice(
            db_session, issued.id, 1, expected_version=issued.version, user_id=1
        )
        assert cancelled.status == InvoiceStatus.cancelled

    async def test_cannot_cancel_paid(self, db_session: AsyncSession):
        from app.modules.invoice import repository as inv_repo
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="G", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        # Manually force paid status
        from app.modules.invoice.models import Invoice
        from sqlalchemy import select
        inv_obj = (await db_session.execute(
            select(Invoice).where(Invoice.id == out.id)
        )).scalar_one()
        inv_obj.status = InvoiceStatus.paid
        await db_session.flush()

        with pytest.raises(InvoiceStateError):
            await inv_service.cancel_invoice(
                db_session, out.id, 1, expected_version=out.version, user_id=1
            )

    async def test_delete_draft(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="H", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        out = await inv_service.create_invoice(
            db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
        )
        await inv_service.delete_invoice(db_session, out.id, 1, user_id=1)
        with pytest.raises(InvoiceNotFoundError):
            await inv_service.get_invoice(db_session, out.id, 1)

    async def test_sequential_inv_doc_numbers(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="I", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()
        doc_numbers = []
        for _ in range(3):
            out = await inv_service.create_invoice(
                db_session, request=InvoiceCreateRequest(customer_id=customer.id), garage_id=1, user_id=1
            )
            issued = await inv_service.issue_invoice(
                db_session, out.id, 1, expected_version=out.version, user_id=1
            )
            doc_numbers.append(issued.doc_number)
        assert len(set(doc_numbers)) == 3
        assert all("INV" in d for d in doc_numbers)


# ---------------------------------------------------------------------------
# Conversion flow tests
# ---------------------------------------------------------------------------

class TestQuotationConversion:

    async def _make_approved_quotation(self, db: AsyncSession, customer_id: int) -> int:
        """Create a quotation, send and approve it. Returns quotation id."""
        lines = [
            QuotationLineCreateRequest(
                description="Labour", quantity=Decimal("1"),
                unit_price_minor=10000,
                discount_percent=Decimal("10"),
                vat_rate=Decimal("20"),
            )
        ]
        q = await quot_service.create_quotation(
            db, request=QuotationCreateRequest(customer_id=customer_id, lines=lines),
            garage_id=1, user_id=1,
        )
        sent = await quot_service.send_quotation(db, q.id, 1, expected_version=q.version, user_id=1)
        await quot_service.approve_quotation(db, q.id, 1, expected_version=sent.version, user_id=1)
        return q.id

    async def test_convert_approved_quotation(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Q1", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        quot_id = await self._make_approved_quotation(db_session, customer.id)
        inv = await inv_service.convert_quotation(db_session, quot_id, 1, user_id=1)

        assert inv.status == InvoiceStatus.draft
        assert inv.quotation_id == quot_id
        assert inv.customer_id == customer.id
        assert len(inv.lines) == 1
        # same totals as quotation: 10000*1*(1-0.1) = 9000; vat = 1800; total = 10800
        assert inv.subtotal_minor == 9000
        assert inv.total_minor == 10800

    async def test_convert_marks_quotation_as_converted(self, db_session: AsyncSession):
        from app.modules.quotation import repository as quot_repo
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Q2", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        quot_id = await self._make_approved_quotation(db_session, customer.id)
        await inv_service.convert_quotation(db_session, quot_id, 1, user_id=1)

        quotation = await quot_repo.get_by_id(db_session, quot_id, garage_id=1)
        assert quotation.status == QuotationStatus.converted

    async def test_convert_twice_raises(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Q3", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        quot_id = await self._make_approved_quotation(db_session, customer.id)
        await inv_service.convert_quotation(db_session, quot_id, 1, user_id=1)

        with pytest.raises(QuotationAlreadyConvertedError):
            await inv_service.convert_quotation(db_session, quot_id, 1, user_id=1)

    async def test_cannot_convert_draft_quotation(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Q4", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        q = await quot_service.create_quotation(
            db_session,
            request=QuotationCreateRequest(customer_id=customer.id),
            garage_id=1, user_id=1,
        )
        with pytest.raises(InvoiceStateError):
            await inv_service.convert_quotation(db_session, q.id, 1, user_id=1)

    async def test_convert_nonexistent_quotation(self, db_session: AsyncSession):
        from app.modules.quotation.service import QuotationNotFoundError
        with pytest.raises(QuotationNotFoundError):
            await inv_service.convert_quotation(db_session, 9999, 1, user_id=1)

    async def test_converted_invoice_can_be_issued(self, db_session: AsyncSession):
        customer = Customer(garage_id=1, type=CustomerType.individual,
                            full_name="Q5", status=CustomerStatus.active)
        db_session.add(customer)
        await db_session.flush()

        quot_id = await self._make_approved_quotation(db_session, customer.id)
        inv = await inv_service.convert_quotation(db_session, quot_id, 1, user_id=1)
        issued = await inv_service.issue_invoice(
            db_session, inv.id, 1, expected_version=inv.version, user_id=1
        )
        assert issued.status == InvoiceStatus.issued
        assert "INV" in issued.doc_number


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestInvoiceEndpoints:

    async def _create_inv(self, client: AsyncClient, token: str, customer_id: int) -> dict:
        r = await client.post(
            "/api/v1/invoices",
            headers={"Authorization": f"Bearer {token}"},
            json={"customer_id": customer_id},
        )
        assert r.status_code == 201, r.text
        return r.json()

    async def test_create_201(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        data = await self._create_inv(inv_client, token, cid)
        assert data["status"] == "draft"
        assert data["version"] == 1

    async def test_list_empty(self, inv_client: AsyncClient):
        token = await _login(inv_client)
        r = await inv_client.get("/api/v1/invoices", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["items"] == []

    async def test_get_invoice(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.get(
            f"/api/v1/invoices/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    async def test_get_not_found(self, inv_client: AsyncClient):
        token = await _login(inv_client)
        r = await inv_client.get(
            "/api/v1/invoices/9999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

    async def test_update_with_if_match(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.patch(
            f"/api/v1/invoices/{created['id']}",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
            json={"notes": "test note"},
        )
        assert r.status_code == 200
        assert r.json()["notes"] == "test note"

    async def test_update_without_if_match_428(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.patch(
            f"/api/v1/invoices/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"notes": "no header"},
        )
        assert r.status_code == 428

    async def test_add_line(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.post(
            f"/api/v1/invoices/{created['id']}/lines",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
            json={
                "description": "Parts", "quantity": "2.000",
                "unit_price_minor": 3000, "discount_percent": "0.00", "vat_rate": "20.00",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["subtotal_minor"] == 6000
        assert data["vat_minor"] == 1200

    async def test_issue_invoice(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.post(
            f"/api/v1/invoices/{created['id']}/issue",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "issued"
        assert "INV" in r.json()["doc_number"]

    async def test_cancel_invoice(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.post(
            f"/api/v1/invoices/{created['id']}/cancel",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(created["version"])},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    async def test_delete_204(self, inv_client: AsyncClient, seeded_inv_db: AsyncSession):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)
        created = await self._create_inv(inv_client, token, cid)
        r = await inv_client.delete(
            f"/api/v1/invoices/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204

    async def test_convert_quotation_via_http(
        self, inv_client: AsyncClient, seeded_inv_db: AsyncSession
    ):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)

        # Create + send + approve quotation
        q_resp = await inv_client.post(
            "/api/v1/quotations",
            headers={"Authorization": f"Bearer {token}"},
            json={"customer_id": cid, "lines": [{
                "description": "Job", "quantity": "1.000",
                "unit_price_minor": 10000, "discount_percent": "0.00", "vat_rate": "20.00",
            }]},
        )
        assert q_resp.status_code == 201
        q = q_resp.json()

        send_r = await inv_client.post(
            f"/api/v1/quotations/{q['id']}/send",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(q["version"])},
        )
        sent = send_r.json()
        approve_r = await inv_client.post(
            f"/api/v1/quotations/{q['id']}/approve",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(sent["version"])},
        )
        assert approve_r.status_code == 200

        # Convert
        conv_r = await inv_client.post(
            f"/api/v1/invoices/from-quotation/{q['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert conv_r.status_code == 201
        inv = conv_r.json()
        assert inv["quotation_id"] == q["id"]
        assert inv["status"] == "draft"
        assert inv["total_minor"] == 12000  # 10000 + 20% VAT

    async def test_convert_twice_returns_409(
        self, inv_client: AsyncClient, seeded_inv_db: AsyncSession
    ):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)

        q_resp = await inv_client.post(
            "/api/v1/quotations",
            headers={"Authorization": f"Bearer {token}"},
            json={"customer_id": cid},
        )
        q = q_resp.json()
        send_r = await inv_client.post(
            f"/api/v1/quotations/{q['id']}/send",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(q["version"])},
        )
        sent = send_r.json()
        await inv_client.post(
            f"/api/v1/quotations/{q['id']}/approve",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(sent["version"])},
        )
        # First conversion
        r1 = await inv_client.post(
            f"/api/v1/invoices/from-quotation/{q['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 201
        # Second conversion → 409
        r2 = await inv_client.post(
            f"/api/v1/invoices/from-quotation/{q['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 409

    async def test_list_filter_by_status(
        self, inv_client: AsyncClient, seeded_inv_db: AsyncSession
    ):
        token = await _login(inv_client)
        cid = await _customer_id(seeded_inv_db)

        i1 = await self._create_inv(inv_client, token, cid)
        i2 = await self._create_inv(inv_client, token, cid)

        await inv_client.post(
            f"/api/v1/invoices/{i1['id']}/issue",
            headers={"Authorization": f"Bearer {token}", "If-Match": str(i1["version"])},
        )
        r = await inv_client.get(
            "/api/v1/invoices?status=issued",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "issued"

    async def test_requires_auth(self, inv_client: AsyncClient):
        r = await inv_client.get("/api/v1/invoices")
        assert r.status_code == 401
