"""Tests for Supplier entity and management — Issue #36."""
from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import Permission, Role, RolePermission

SUPPLIER_PERMISSIONS = ("supplier.read", "supplier.create", "supplier.update", "supplier.delete")
PART_PERMISSIONS = ("part.read", "part.create", "part.update", "part.delete")
ALL_PERMISSIONS = SUPPLIER_PERMISSIONS + PART_PERMISSIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def supplier_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    role_row = (
        await seeded_db.execute(select(Role).where(Role.code == "admin"))
    ).scalar_one()

    for code in ALL_PERMISSIONS:
        perm = Permission(
            code=code,
            resource=code.split(".")[0],
            action=".".join(code.split(".")[1:]),
            description="",
        )
        seeded_db.add(perm)
    await seeded_db.flush()

    for code in ALL_PERMISSIONS:
        perm_row = (
            await seeded_db.execute(select(Permission).where(Permission.code == code))
        ).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm_row.id))
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def supplier_client(
    supplier_seeded_db: AsyncSession, mock_redis
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield supplier_seeded_db

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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Garage-ID": "1"}


async def _create_supplier(
    client: AsyncClient,
    token: str,
    name: str = "Acme Parts",
    **kwargs,
) -> dict:
    body = {
        "name": name,
        "email": "acme@example.com",
        "phone": "+212600000001",
        "payment_terms_days": 30,
        "average_delivery_days": 5,
        **kwargs,
    }
    resp = await client.post("/api/v1/suppliers", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_part(
    client: AsyncClient,
    token: str,
    sku: str = "P-SUPP-001",
) -> dict:
    resp = await client.post(
        "/api/v1/parts",
        json={
            "sku_code": sku,
            "name": f"Test Part {sku}",
            "purchase_price_minor": 1000,
            "selling_price_minor": 1500,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# TestSupplierCRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSupplierCRUD:
    async def test_create_supplier(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        supplier = await _create_supplier(supplier_client, token)

        assert supplier["name"] == "Acme Parts"
        assert supplier["email"] == "acme@example.com"
        assert supplier["payment_terms_days"] == 30
        assert supplier["average_delivery_days"] == 5
        assert supplier["status"] == "active"
        assert supplier["version"] == 1
        assert "id" in supplier

    async def test_list_suppliers(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        await _create_supplier(supplier_client, token, name="Alpha Parts")
        await _create_supplier(supplier_client, token, name="Beta Parts")

        resp = await supplier_client.get("/api/v1/suppliers", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_get_supplier(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        created = await _create_supplier(supplier_client, token)
        sid = created["id"]

        resp = await supplier_client.get(f"/api/v1/suppliers/{sid}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == sid

    async def test_get_supplier_not_found(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await supplier_client.get(f"/api/v1/suppliers/{fake_id}", headers=_auth(token))
        assert resp.status_code == 404

    async def test_update_supplier(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        created = await _create_supplier(supplier_client, token)
        sid = created["id"]

        resp = await supplier_client.put(
            f"/api/v1/suppliers/{sid}",
            json={"version": 1, "name": "Updated Parts", "payment_terms_days": 45},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Parts"
        assert data["payment_terms_days"] == 45
        assert data["version"] == 2

    async def test_delete_supplier(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        created = await _create_supplier(supplier_client, token)
        sid = created["id"]

        resp = await supplier_client.delete(f"/api/v1/suppliers/{sid}", headers=_auth(token))
        assert resp.status_code == 204

        # Soft-deleted: no longer visible
        resp2 = await supplier_client.get(f"/api/v1/suppliers/{sid}", headers=_auth(token))
        assert resp2.status_code == 404

    async def test_search_suppliers_by_name(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        await _create_supplier(supplier_client, token, name="Mega Supplies")
        await _create_supplier(supplier_client, token, name="Tiny Parts Co")

        resp = await supplier_client.get(
            "/api/v1/suppliers?search=mega", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Mega Supplies"

    async def test_filter_by_status(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        s = await _create_supplier(supplier_client, token)

        # Deactivate it
        await supplier_client.put(
            f"/api/v1/suppliers/{s['id']}",
            json={"version": 1, "status": "inactive"},
            headers=_auth(token),
        )

        resp_active = await supplier_client.get(
            "/api/v1/suppliers?status=active", headers=_auth(token)
        )
        assert resp_active.json()["total"] == 0

        resp_inactive = await supplier_client.get(
            "/api/v1/suppliers?status=inactive", headers=_auth(token)
        )
        assert resp_inactive.json()["total"] == 1


# ---------------------------------------------------------------------------
# TestSupplierVersionConflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSupplierVersionConflict:
    async def test_version_conflict_on_update(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        created = await _create_supplier(supplier_client, token)
        sid = created["id"]

        resp = await supplier_client.put(
            f"/api/v1/suppliers/{sid}",
            json={"version": 99, "name": "Should Fail"},
            headers=_auth(token),
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["code"] == "version_conflict"
        assert body["detail"]["current_version"] == 1


# ---------------------------------------------------------------------------
# TestSupplierPriceHistory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSupplierPriceHistory:
    async def test_add_price_entry(self, supplier_client: AsyncClient) -> None:
        token = await _login(supplier_client)
        supplier = await _create_supplier(supplier_client, token)
        part = await _create_part(supplier_client, token)

        resp = await supplier_client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 5000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit_price_minor"] == 5000
        assert data["currency"] == "MAD"
        assert data["effective_from"] == "2025-01-01"
        assert data["effective_to"] is None
        assert data["part_name"] == f"Test Part {part['sku_code']}"

    async def test_add_price_closes_previous(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        supplier = await _create_supplier(supplier_client, token)
        part = await _create_part(supplier_client, token, sku="P-CLOSE-001")

        # First price: open (no effective_to)
        await supplier_client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 5000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )

        # Second price: should close the first
        await supplier_client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 6000,
                "currency": "MAD",
                "effective_from": "2025-06-01",
            },
            headers=_auth(token),
        )

        resp = await supplier_client.get(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        entries = resp.json()
        # Two entries for this part
        part_entries = [e for e in entries if e["part_public_id"] == part["id"]]
        assert len(part_entries) == 2

        # Find the first price (lower price) — should have effective_to set
        old_entry = next(e for e in part_entries if e["unit_price_minor"] == 5000)
        assert old_entry["effective_to"] == "2025-05-31"

        # New entry should be open
        new_entry = next(e for e in part_entries if e["unit_price_minor"] == 6000)
        assert new_entry["effective_to"] is None

    async def test_price_history_for_unknown_supplier(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        fake = "00000000-0000-0000-0000-000000000001"
        resp = await supplier_client.get(
            f"/api/v1/suppliers/{fake}/prices", headers=_auth(token)
        )
        assert resp.status_code == 404

    async def test_add_price_for_unknown_part(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        supplier = await _create_supplier(supplier_client, token)
        fake_part = "00000000-0000-0000-0000-000000000002"

        resp = await supplier_client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": fake_part,
                "unit_price_minor": 5000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestHistoricalPriceQuery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHistoricalPriceQuery:
    async def _setup(self, client: AsyncClient, token: str) -> tuple[dict, dict]:
        supplier = await _create_supplier(client, token, name="Hist Supplier")
        part = await _create_part(client, token, sku="P-HIST-001")

        # Price 1: 2025-01-01 → 2025-05-31 (closed by price 2)
        await client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 4000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )
        # Price 2: 2025-06-01 → open
        await client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 4500,
                "currency": "MAD",
                "effective_from": "2025-06-01",
            },
            headers=_auth(token),
        )
        return supplier, part

    async def test_historical_price_returns_correct_entry(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        supplier, part = await self._setup(supplier_client, token)

        # Query at a date in the first period
        resp = await supplier_client.get(
            f"/api/v1/parts/{part['id']}/supplier-prices?at=2025-03-15",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["unit_price_minor"] == 4000

    async def test_current_price_returned_without_at_param(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        supplier, part = await self._setup(supplier_client, token)

        # Latest price should be 4500 (effective from 2025-06-01)
        resp = await supplier_client.get(
            f"/api/v1/parts/{part['id']}/supplier-prices",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        items = resp.json()
        # Should return the 4500 price (currently open)
        assert any(i["unit_price_minor"] == 4500 for i in items)

    async def test_no_price_before_first_entry(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        supplier, part = await self._setup(supplier_client, token)

        # Date before any price
        resp = await supplier_client.get(
            f"/api/v1/parts/{part['id']}/supplier-prices?at=2024-01-01",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# TestPartPriceComparison
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPartPriceComparison:
    async def test_comparison_sorted_by_price(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        s1 = await _create_supplier(supplier_client, token, name="Cheap Supplier")
        s2 = await _create_supplier(supplier_client, token, name="Pricey Supplier")
        part = await _create_part(supplier_client, token, sku="P-CMP-001")

        await supplier_client.post(
            f"/api/v1/suppliers/{s2['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 9000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )
        await supplier_client.post(
            f"/api/v1/suppliers/{s1['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 3000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )

        resp = await supplier_client.get(
            f"/api/v1/parts/{part['id']}/supplier-prices",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        # Sorted ascending by price
        assert items[0]["unit_price_minor"] == 3000
        assert items[1]["unit_price_minor"] == 9000
        assert items[0]["supplier_name"] == "Cheap Supplier"

    async def test_comparison_excludes_inactive_supplier(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        supplier = await _create_supplier(supplier_client, token, name="Inactive Co")
        part = await _create_part(supplier_client, token, sku="P-INACT-001")

        await supplier_client.post(
            f"/api/v1/suppliers/{supplier['id']}/prices",
            json={
                "part_public_id": part["id"],
                "unit_price_minor": 5000,
                "currency": "MAD",
                "effective_from": "2025-01-01",
            },
            headers=_auth(token),
        )

        # Deactivate supplier
        await supplier_client.put(
            f"/api/v1/suppliers/{supplier['id']}",
            json={"version": 1, "status": "inactive"},
            headers=_auth(token),
        )

        resp = await supplier_client.get(
            f"/api/v1/parts/{part['id']}/supplier-prices",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_comparison_unknown_part(
        self, supplier_client: AsyncClient
    ) -> None:
        token = await _login(supplier_client)
        fake = "00000000-0000-0000-0000-000000000099"
        resp = await supplier_client.get(
            f"/api/v1/parts/{fake}/supplier-prices",
            headers=_auth(token),
        )
        assert resp.status_code == 404
