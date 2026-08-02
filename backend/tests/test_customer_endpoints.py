"""Integration tests for the customer module HTTP endpoints.

These tests log in via the existing seeded admin and exercise the full
request → service → DB path. The fixture extends `seeded_db` with the
customer permission catalog so the admin role grants access to the
customer endpoints.
"""
from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import Permission, Role, RolePermission

CUSTOMER_PERMISSIONS = (
    "customer.read",
    "customer.create",
    "customer.update",
    "customer.delete",
    "customer.credit_limit.update",
    "customer.balance.read",
)


@pytest_asyncio.fixture
async def customer_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    """Extend the shared seeded_db with customer permissions on the admin role."""
    role_row = (await seeded_db.execute(
        select(Role).where(Role.code == "admin")
    )).scalar_one()

    for code in CUSTOMER_PERMISSIONS:
        perm = Permission(code=code, resource=code.split(".")[0], action=code, description="")
        seeded_db.add(perm)
    await seeded_db.flush()

    for code in CUSTOMER_PERMISSIONS:
        perm = (await seeded_db.execute(
            select(Permission).where(Permission.code == code)
        )).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm.id))
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def customer_client(
    customer_seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield customer_seeded_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Test1234!"},
        headers={"X-Garage-ID": "1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Authentication / permission gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthGates:
    async def test_list_requires_auth(self, customer_client: AsyncClient) -> None:
        resp = await customer_client.get("/api/v1/customers")
        assert resp.status_code == 401

    async def test_create_requires_auth(self, customer_client: AsyncClient) -> None:
        resp = await customer_client.post(
            "/api/v1/customers",
            json={"type": "individual", "full_name": "x"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListAndGet:
    async def test_empty_list(self, customer_client: AsyncClient) -> None:
        token = await _login(customer_client)
        resp = await customer_client.get("/api/v1/customers", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"items": [], "total": 0, "page": 1, "page_size": 20}

    async def test_get_unknown_returns_404(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.get(
            "/api/v1/customers/00000000-0000-0000-0000-000000000000",
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create + duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateEndpoint:
    async def test_create_minimal_returns_201(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "Alice",
                "fiscal_id": "FID-ALICE", "phone_e164": "+33611111111",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_name"] == "Alice"
        assert data["version"] == 1
        assert data["status"] == "active"

    async def test_create_with_contacts(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "company",
                "full_name": "ACME Auto",
                "company_name": "ACME Auto SARL",
                "fiscal_id": "12345678901234",
                "phone_e164": "+33612345678",
                "contacts": [
                    {"channel": "phone", "value": "+212611111111", "is_primary": True},
                    {"channel": "email", "value": "c@a.com"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["contacts"]) == 2

    async def test_invalid_phone_format_rejected(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "individual", "full_name": "X", "phone_e164": "0612345678"},
        )
        assert resp.status_code == 422

    async def test_company_without_company_name_rejected(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "company", "full_name": "X"},
        )
        assert resp.status_code == 422

    async def test_duplicate_returns_409_with_merge_prompt(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "Original",
                "fiscal_id": "F-1", "phone_e164": "+33611111111",
            },
        )
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "Duplicate",
                "fiscal_id": "F-1", "phone_e164": "+33611111111",
            },
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "duplicate_customer"
        assert body["match_reason"] == "phone_and_fiscal_id"
        assert body["existing"]["full_name"] == "Original"


# ---------------------------------------------------------------------------
# Update + optimistic locking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpdateEndpoint:
    async def _create(self, client: AsyncClient, token: str) -> dict:
        resp = await client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "Original",
                "fiscal_id": "FID-UPDATE", "phone_e164": "+33611111111",
            },
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_update_bumps_version(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        created = await self._create(customer_client, token)

        resp = await customer_client.patch(
            f"/api/v1/customers/{created['id']}",
            headers=_auth(token),
            json={"version": 1, "full_name": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated"
        assert resp.json()["version"] == 2

    async def test_stale_version_returns_409(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        created = await self._create(customer_client, token)

        # First update lands; version becomes 2
        await customer_client.patch(
            f"/api/v1/customers/{created['id']}",
            headers=_auth(token),
            json={"version": 1, "full_name": "First"},
        )
        # Second tries with stale version 1
        resp = await customer_client.patch(
            f"/api/v1/customers/{created['id']}",
            headers=_auth(token),
            json={"version": 1, "full_name": "Second"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == "stale_version"
        assert detail["current_version"] == 2

    async def test_update_unknown_returns_404(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.patch(
            "/api/v1/customers/00000000-0000-0000-0000-000000000000",
            headers=_auth(token),
            json={"version": 1, "full_name": "X"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete + restore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeleteRestore:
    async def test_delete_then_get_returns_404(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        created = (await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "DeleteMe",
                "fiscal_id": "FID-DELETE", "phone_e164": "+33611111111",
            },
        )).json()
        pid = created["id"]

        resp = await customer_client.delete(
            f"/api/v1/customers/{pid}", headers=_auth(token)
        )
        assert resp.status_code == 204

        gone = await customer_client.get(
            f"/api/v1/customers/{pid}", headers=_auth(token)
        )
        assert gone.status_code == 404

    async def test_restore_brings_record_back(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        created = (await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "Restore",
                "fiscal_id": "FID-RESTORE", "phone_e164": "+33611111111",
            },
        )).json()
        pid = created["id"]
        await customer_client.delete(f"/api/v1/customers/{pid}", headers=_auth(token))

        resp = await customer_client.post(
            f"/api/v1/customers/{pid}/restore", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearch:
    async def test_search_matches_partial_name(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        for i, name in enumerate(("Sami Hammoussi", "Mohammed Ali", "Atlas Auto")):
            await customer_client.post(
                "/api/v1/customers",
                headers=_auth(token),
                json={
                    "type": "individual", "full_name": name,
                    "fiscal_id": f"FID-SEARCH-{i}", "phone_e164": f"+3361111111{i}",
                },
            )

        resp = await customer_client.get(
            "/api/v1/customers", params={"q": "Sami"}, headers=_auth(token)
        )
        assert resp.status_code == 200
        names = [r["full_name"] for r in resp.json()["items"]]
        assert "Sami Hammoussi" in names
        assert "Mohammed Ali" not in names


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuditPersisted:
    async def test_create_writes_audit_row(
        self,
        customer_client: AsyncClient,
        customer_seeded_db: AsyncSession,
    ) -> None:
        token = await _login(customer_client)
        await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "Audited",
                "fiscal_id": "FID-AUDITED", "phone_e164": "+33611111111",
            },
        )

        result = await customer_seeded_db.execute(
            select(AuditLog).where(
                AuditLog.component == "customer", AuditLog.action == "create"
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].entity_type == "customer"
        # actor was resolved from the JWT
        assert rows[0].user_id is not None


# ---------------------------------------------------------------------------
# Bulk import from Excel
# ---------------------------------------------------------------------------


def _build_xlsx(rows: list[list]) -> bytes:
    """Build an in-memory .xlsx workbook from a list of rows (first row = header)."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_IMPORT_HEADER = [
    "Nom",
    "Prénom",
    "Nom de l'entreprise",
    "Téléphone",
    "E-mail",
    "Adresse",
    "Code postal",
    "Ville",
]


@pytest.mark.asyncio
class TestImportEndpoint:
    async def test_import_creates_customers(self, customer_client: AsyncClient) -> None:
        token = await _login(customer_client)
        content = _build_xlsx(
            [
                _IMPORT_HEADER,
                ["Dupont", "Jean", None, "+33760481234", "jean@example.com", "1 Rue X", 13015, "Marseille"],
                [None, None, "AUTOGRIFF", None, None, "5 Bd Y", 67000, "Strasbourg"],
            ]
        )
        resp = await customer_client.post(
            "/api/v1/customers/import",
            headers=_auth(token),
            files={"file": ("clients.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["created"] == 2
        assert data["skipped"] == 0
        assert data["errors"] == []

        # The company row was classified as a company.
        listing = await customer_client.get(
            "/api/v1/customers", headers=_auth(token), params={"q": "AUTOGRIFF"}
        )
        items = listing.json()["items"]
        assert any(i["type"] == "company" and i["company_name"] == "AUTOGRIFF" for i in items)

    async def test_import_tolerates_empty_and_bad_cells(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        content = _build_xlsx(
            [
                _IMPORT_HEADER,
                # Fully empty row → ignored silently.
                [None, None, None, None, None, None, None, None],
                # Invalid phone + invalid email are dropped, customer still created.
                ["Martin", "Luc", None, "0612345678", "not-an-email", None, None, "Lyon"],
                # No name at all but has data → error row.
                [None, None, None, "+33111111111", None, "some street", None, None],
            ]
        )
        resp = await customer_client.post(
            "/api/v1/customers/import",
            headers=_auth(token),
            files={"file": ("clients.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["row"] == 4

    async def test_import_skips_duplicates(self, customer_client: AsyncClient) -> None:
        token = await _login(customer_client)
        rows = [
            _IMPORT_HEADER,
            ["Bara", "Hakim", None, "+33760000001", "hakim@example.com", None, None, None],
            # Same phone as above → duplicate, skipped.
            ["Bara", "Hakim", None, "+33760000001", None, None, None, None],
        ]
        content = _build_xlsx(rows)
        resp = await customer_client.post(
            "/api/v1/customers/import",
            headers=_auth(token),
            files={"file": ("clients.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    async def test_import_skips_name_duplicates_without_contact(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        # Rows carry neither phone nor email — dedup must fall back to name.
        rows = [
            _IMPORT_HEADER,
            ["Achit", "Mouloud", None, None, None, "1", 13015, "Marseille"],
            # Same name (different case) → duplicate within the file.
            ["ACHIT", "MOULOUD", None, None, None, "1", 13015, "Marseille"],
        ]
        first = await customer_client.post(
            "/api/v1/customers/import",
            headers=_auth(token),
            files={"file": ("clients.xlsx", _build_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert first.status_code == 200, first.text
        assert first.json()["created"] == 1
        assert first.json()["skipped"] == 1

        # Re-importing the same list must create nothing (already in the DB).
        second = await customer_client.post(
            "/api/v1/customers/import",
            headers=_auth(token),
            files={"file": ("clients.xlsx", _build_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert second.status_code == 200, second.text
        assert second.json()["created"] == 0
        assert second.json()["skipped"] == 2

    async def test_import_rejects_non_xlsx(self, customer_client: AsyncClient) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers/import",
            headers=_auth(token),
            files={"file": ("clients.csv", b"a,b,c", "text/csv")},
        )
        assert resp.status_code == 400

    async def test_import_requires_auth(self, customer_client: AsyncClient) -> None:
        content = _build_xlsx([_IMPORT_HEADER])
        resp = await customer_client.post(
            "/api/v1/customers/import",
            files={"file": ("clients.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 401
