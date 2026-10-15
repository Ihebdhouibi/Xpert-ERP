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
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password

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

    async def test_individual_with_only_name_and_cin_returns_201(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "individual", "full_name": "Alice", "fiscal_id": "AB123456"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["fiscal_id"] == "AB123456"
        assert data["phone_e164"] is None
        assert data["email"] is None
        assert data["address"] is None
        assert data["credit_limit_minor"] == 0

    async def test_company_with_only_contact_company_and_siret_returns_201(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "company",
                "full_name": "Karim Benali",
                "company_name": "Garage Atlas SARL",
                "fiscal_id": "12345678901234",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["company_name"] == "Garage Atlas SARL"
        assert data["phone_e164"] is None

    async def test_individual_without_cin_rejected(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "individual", "full_name": "Alice", "phone_e164": "+33611111111"},
        )
        assert resp.status_code == 422

    async def test_company_without_siret_rejected(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "company", "full_name": "Karim", "company_name": "Atlas SARL"},
        )
        assert resp.status_code == 422

    async def test_invalid_phone_format_rejected(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={
                "type": "individual", "full_name": "X",
                "fiscal_id": "FID-BADPHONE", "phone_e164": "0612345678",
            },
        )
        assert resp.status_code == 422

    async def test_company_without_company_name_rejected(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "company", "full_name": "X", "fiscal_id": "12345678901234"},
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
# Quick create (walk-in customer from just a name)
# ---------------------------------------------------------------------------


async def _login_as_read_only(client: AsyncClient, db: AsyncSession) -> str:
    """Log in as a user whose role only holds `customer.read`."""
    role = Role(code="customer_reader", display_name="Customer reader", is_system=False)
    db.add(role)
    await db.flush()
    read_perm = (await db.execute(
        select(Permission).where(Permission.code == "customer.read")
    )).scalar_one()
    db.add(RolePermission(role_id=role.id, permission_id=read_perm.id))
    user = AppUser(
        garage_id=1,
        email="reader@test.com",
        full_name="Reader",
        password_hash=hash_password("Test1234!"),
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "reader@test.com", "password": "Test1234!"},
        headers={"X-Garage-ID": "1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
class TestQuickCreateEndpoint:
    async def test_name_only_returns_201_with_a_usable_customer(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers/quick",
            headers=_auth(token),
            json={"full_name": "Mohamed"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["full_name"] == "Mohamed"
        assert data["type"] == "individual"
        assert data["segment"] == "passager"
        assert data["status"] == "active"
        assert data["fiscal_id"] is None
        assert data["phone_e164"] is None
        assert data["email"] is None
        assert data["company_name"] is None
        assert data["credit_limit_minor"] == 0
        assert data["version"] == 1
        # The facture / devis popups use int_id as the document's customer_id.
        assert isinstance(data["int_id"], int)

    async def test_new_customer_shows_up_in_the_picker_search(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        created = (await customer_client.post(
            "/api/v1/customers/quick",
            headers=_auth(token),
            json={"full_name": "Mohamed Benali"},
        )).json()

        # Same query the client picker runs while typing.
        resp = await customer_client.get(
            "/api/v1/customers",
            headers=_auth(token),
            params={"q": "Mohamed", "status": "active", "page_size": 20},
        )
        assert resp.status_code == 200
        assert created["int_id"] in [c["int_id"] for c in resp.json()["items"]]

    async def test_name_is_trimmed(self, customer_client: AsyncClient) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers/quick",
            headers=_auth(token),
            json={"full_name": "  Mohamed  "},
        )
        assert resp.status_code == 201
        assert resp.json()["full_name"] == "Mohamed"

    @pytest.mark.parametrize("body", [{}, {"full_name": ""}, {"full_name": "   "}])
    async def test_missing_or_blank_name_rejected(
        self, customer_client: AsyncClient, body: dict
    ) -> None:
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers/quick", headers=_auth(token), json=body
        )
        assert resp.status_code == 422

    async def test_requires_auth(self, customer_client: AsyncClient) -> None:
        resp = await customer_client.post(
            "/api/v1/customers/quick", json={"full_name": "Mohamed"}
        )
        assert resp.status_code == 401

    async def test_requires_customer_create_permission(
        self, customer_client: AsyncClient, customer_seeded_db: AsyncSession
    ) -> None:
        token = await _login_as_read_only(customer_client, customer_seeded_db)

        # The token is valid (reading works) but creating is forbidden.
        listing = await customer_client.get("/api/v1/customers", headers=_auth(token))
        assert listing.status_code == 200
        resp = await customer_client.post(
            "/api/v1/customers/quick",
            headers=_auth(token),
            json={"full_name": "Mohamed"},
        )
        assert resp.status_code == 403

    async def test_walk_in_can_be_completed_later_without_a_cin(
        self, customer_client: AsyncClient
    ) -> None:
        """The edit form sends the whole record, with the CIN as null for a walk-in."""
        token = await _login(customer_client)
        created = (await customer_client.post(
            "/api/v1/customers/quick",
            headers=_auth(token),
            json={"full_name": "Mohamed"},
        )).json()

        resp = await customer_client.patch(
            f"/api/v1/customers/{created['id']}",
            headers=_auth(token),
            json={
                "version": created["version"],
                "full_name": "Mohamed",
                "company_name": None,
                "fiscal_id": None,
                "email": None,
                "phone_e164": "+33611111111",
                "address": None,
                "segment": "passager",
                "status": "active",
                "notes": None,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["phone_e164"] == "+33611111111"
        assert data["fiscal_id"] is None
        assert data["segment"] == "passager"
        assert data["version"] == 2

    async def test_names_never_identify_a_client_but_the_cin_does(
        self, customer_client: AsyncClient
    ) -> None:
        """Two walk-ins may share a name; once one gets a CIN, no one else can have it."""
        token = await _login(customer_client)

        async def new_walk_in() -> dict:
            resp = await customer_client.post(
                "/api/v1/customers/quick",
                headers=_auth(token),
                json={"full_name": "Mohamed"},
            )
            assert resp.status_code == 201, resp.text
            return resp.json()

        first, second = await new_walk_in(), await new_walk_in()
        assert first["id"] != second["id"]  # same name, still two clients

        async def set_cin(customer: dict, cin: str):
            return await customer_client.patch(
                f"/api/v1/customers/{customer['id']}",
                headers=_auth(token),
                json={"version": customer["version"], "fiscal_id": cin},
            )

        assert (await set_cin(first, "AB123456")).status_code == 200
        clash = await set_cin(second, "AB123456")
        assert clash.status_code == 409
        assert clash.json()["detail"]["code"] == "fiscal_id_taken"

    async def test_regular_create_still_demands_a_cin(
        self, customer_client: AsyncClient
    ) -> None:
        """The quick path must not have loosened POST /customers."""
        token = await _login(customer_client)
        resp = await customer_client.post(
            "/api/v1/customers",
            headers=_auth(token),
            json={"type": "individual", "full_name": "Mohamed"},
        )
        assert resp.status_code == 422


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

    async def test_update_can_clear_phone(
        self, customer_client: AsyncClient
    ) -> None:
        token = await _login(customer_client)
        created = await self._create(customer_client, token)
        assert created["phone_e164"] == "+33611111111"

        resp = await customer_client.patch(
            f"/api/v1/customers/{created['id']}",
            headers=_auth(token),
            json={"version": 1, "phone_e164": None},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["phone_e164"] is None
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
