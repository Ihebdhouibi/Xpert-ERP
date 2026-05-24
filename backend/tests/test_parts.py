"""Tests for Parts catalog — Issue #24."""
from __future__ import annotations

import uuid
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
from app.modules.auth.models import Permission, Role, RolePermission

PART_PERMISSIONS = (
    "part.read",
    "part.create",
    "part.update",
    "part.delete",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def parts_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    role_row = (await seeded_db.execute(
        select(Role).where(Role.code == "admin")
    )).scalar_one()

    for code in PART_PERMISSIONS:
        perm = Permission(
            code=code,
            resource=code.split(".")[0],
            action=".".join(code.split(".")[1:]),
            description="",
        )
        seeded_db.add(perm)
    await seeded_db.flush()

    for code in PART_PERMISSIONS:
        perm_row = (await seeded_db.execute(
            select(Permission).where(Permission.code == code)
        )).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm_row.id))
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def parts_client(
    parts_seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield parts_seeded_db

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


async def _create_part(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {
        "sku_code": "TEST-001",
        "name": "Filtre à huile",
        "purchase_price_minor": 1500,
        "selling_price_minor": 2500,
        **overrides,
    }
    resp = await client.post("/api/v1/parts", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_category(client: AsyncClient, token: str, name: str = "Filtres") -> dict:
    resp = await client.post(
        "/api/v1/part-categories",
        json={"name": name},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Category tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPartCategories:
    async def test_create_category(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        cat = await _create_category(parts_client, token)
        assert cat["name"] == "Filtres"
        assert cat["parent_id"] is None

    async def test_create_child_category(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        parent = await _create_category(parts_client, token, name="Moteur")
        resp = await parts_client.post(
            "/api/v1/part-categories",
            json={"name": "Filtres moteur", "parent_id": parent["id"]},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["parent_id"] == parent["id"]

    async def test_create_category_invalid_parent_404(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        resp = await parts_client.post(
            "/api/v1/part-categories",
            json={"name": "Orphan", "parent_id": 99999},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    async def test_list_categories(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        await _create_category(parts_client, token, name="CatA")
        await _create_category(parts_client, token, name="CatB")
        resp = await parts_client.get("/api/v1/part-categories", headers=_auth(token))
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "CatA" in names
        assert "CatB" in names

    async def test_update_category(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        cat = await _create_category(parts_client, token)
        resp = await parts_client.patch(
            f"/api/v1/part-categories/{cat['id']}",
            json={"name": "Filtres Updated"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Filtres Updated"

    async def test_delete_empty_category(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        cat = await _create_category(parts_client, token, name="ToDelete")
        resp = await parts_client.delete(
            f"/api/v1/part-categories/{cat['id']}",
            headers=_auth(token),
        )
        assert resp.status_code == 204

    async def test_delete_category_with_parts_fails(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        cat = await _create_category(parts_client, token, name="WithParts")
        await _create_part(parts_client, token, sku_code="SKU-CAT", category_id=cat["id"])
        resp = await parts_client.delete(
            f"/api/v1/part-categories/{cat['id']}",
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Part CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPartCRUD:
    async def test_create_part(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part = await _create_part(parts_client, token)
        assert part["sku_code"] == "TEST-001"
        assert part["name"] == "Filtre à huile"
        assert part["purchase_price_minor"] == 1500
        assert part["selling_price_minor"] == 2500
        assert part["status"] == "active"
        assert part["version"] == 1
        assert "id" in part

    async def test_sku_uppercased(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part = await _create_part(parts_client, token, sku_code="abc-123")
        assert part["sku_code"] == "ABC-123"

    async def test_duplicate_sku_returns_409(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        await _create_part(parts_client, token, sku_code="DUP-001")
        resp = await parts_client.post(
            "/api/v1/parts",
            json={
                "sku_code": "DUP-001",
                "name": "Duplicate",
                "purchase_price_minor": 100,
                "selling_price_minor": 200,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "sku_conflict"

    async def test_float_price_returns_422(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        resp = await parts_client.post(
            "/api/v1/parts",
            json={
                "sku_code": "FLOAT-001",
                "name": "Float Price",
                "purchase_price_minor": 9.99,
                "selling_price_minor": 1499,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_float_selling_price_returns_422(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        resp = await parts_client.post(
            "/api/v1/parts",
            json={
                "sku_code": "FLOAT-002",
                "name": "Float Sell",
                "purchase_price_minor": 1000,
                "selling_price_minor": 19.95,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_list_parts(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        await _create_part(parts_client, token, sku_code="LIST-001", name="Alpha Part")
        await _create_part(parts_client, token, sku_code="LIST-002", name="Beta Part")
        resp = await parts_client.get("/api/v1/parts", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert "items" in data

    async def test_search_by_name(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        await _create_part(parts_client, token, sku_code="SRH-001", name="Unique Plaquette")
        resp = await parts_client.get(
            "/api/v1/parts?search=plaquette", headers=_auth(token)
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any("Plaquette" in p["name"] for p in items)

    async def test_search_by_sku(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        await _create_part(parts_client, token, sku_code="SKUSRH-99", name="SKU Search Part")
        resp = await parts_client.get(
            "/api/v1/parts?search=SKUSRH", headers=_auth(token)
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(p["sku_code"] == "SKUSRH-99" for p in items)

    async def test_filter_by_category(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        cat = await _create_category(parts_client, token, name="FilterCat")
        await _create_part(parts_client, token, sku_code="CAT-001", name="CatPart", category_id=cat["id"])
        resp = await parts_client.get(
            f"/api/v1/parts?category_id={cat['id']}", headers=_auth(token)
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(p["category_id"] == cat["id"] for p in items)
        assert len(items) >= 1

    async def test_get_part(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        created = await _create_part(parts_client, token, sku_code="GET-001")
        resp = await parts_client.get(
            f"/api/v1/parts/{created['id']}", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["sku_code"] == "GET-001"

    async def test_get_unknown_part_404(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        resp = await parts_client.get(
            f"/api/v1/parts/{uuid.uuid4()}", headers=_auth(token)
        )
        assert resp.status_code == 404

    async def test_update_part(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part = await _create_part(parts_client, token, sku_code="UPD-001")
        resp = await parts_client.patch(
            f"/api/v1/parts/{part['id']}?version=1",
            json={"name": "Updated Name", "selling_price_minor": 3000},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["selling_price_minor"] == 3000
        assert data["version"] == 2

    async def test_update_version_conflict(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part = await _create_part(parts_client, token, sku_code="VER-001")
        resp = await parts_client.patch(
            f"/api/v1/parts/{part['id']}?version=99",
            json={"name": "Stale"},
            headers=_auth(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "version_conflict"

    async def test_soft_delete_part(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part = await _create_part(parts_client, token, sku_code="DEL-001")
        resp = await parts_client.delete(
            f"/api/v1/parts/{part['id']}", headers=_auth(token)
        )
        assert resp.status_code == 204
        resp2 = await parts_client.get(
            f"/api/v1/parts/{part['id']}", headers=_auth(token)
        )
        assert resp2.status_code == 404

    async def test_requires_auth(self, parts_client: AsyncClient):
        resp = await parts_client.get("/api/v1/parts")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Equivalents tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEquivalents:
    async def test_link_and_list_equivalents(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part_a = await _create_part(parts_client, token, sku_code="EQA-001", name="Part A")
        part_b = await _create_part(parts_client, token, sku_code="EQB-001", name="Part B")

        resp = await parts_client.post(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            json={"target_id": part_b["id"]},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        ids = [p["id"] for p in resp.json()]
        assert part_b["id"] in ids

    async def test_equivalent_bidirectional(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part_a = await _create_part(parts_client, token, sku_code="BIA-001", name="Bi A")
        part_b = await _create_part(parts_client, token, sku_code="BIB-001", name="Bi B")

        await parts_client.post(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            json={"target_id": part_b["id"]},
            headers=_auth(token),
        )

        # Query from B's perspective
        resp_b = await parts_client.get(
            f"/api/v1/parts/{part_b['id']}/equivalents",
            headers=_auth(token),
        )
        assert resp_b.status_code == 200
        ids = [p["id"] for p in resp_b.json()]
        assert part_a["id"] in ids

    async def test_self_link_returns_422(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part = await _create_part(parts_client, token, sku_code="SELF-001", name="Self")
        resp = await parts_client.post(
            f"/api/v1/parts/{part['id']}/equivalents",
            json={"target_id": part["id"]},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_duplicate_link_returns_409(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part_a = await _create_part(parts_client, token, sku_code="DUPA-001", name="DupA")
        part_b = await _create_part(parts_client, token, sku_code="DUPB-001", name="DupB")

        await parts_client.post(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            json={"target_id": part_b["id"]},
            headers=_auth(token),
        )
        resp = await parts_client.post(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            json={"target_id": part_b["id"]},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    async def test_unlink_equivalent(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part_a = await _create_part(parts_client, token, sku_code="UNLK-A", name="Unlink A")
        part_b = await _create_part(parts_client, token, sku_code="UNLK-B", name="Unlink B")

        await parts_client.post(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            json={"target_id": part_b["id"]},
            headers=_auth(token),
        )
        resp = await parts_client.delete(
            f"/api/v1/parts/{part_a['id']}/equivalents/{part_b['id']}",
            headers=_auth(token),
        )
        assert resp.status_code == 204

        resp_list = await parts_client.get(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            headers=_auth(token),
        )
        assert resp_list.json() == []

    async def test_part_detail_includes_equivalents(self, parts_client: AsyncClient):
        token = await _login(parts_client)
        part_a = await _create_part(parts_client, token, sku_code="DET-A", name="Detail A")
        part_b = await _create_part(parts_client, token, sku_code="DET-B", name="Detail B")

        await parts_client.post(
            f"/api/v1/parts/{part_a['id']}/equivalents",
            json={"target_id": part_b["id"]},
            headers=_auth(token),
        )
        resp = await parts_client.get(
            f"/api/v1/parts/{part_a['id']}", headers=_auth(token)
        )
        assert resp.status_code == 200
        equiv_ids = [p["id"] for p in resp.json()["equivalents"]]
        assert part_b["id"] in equiv_ids
