"""Integration tests for repair order HTTP endpoints.

Tests exercise the full request → service → DB path using the in-memory
SQLite test DB and the same patterns as test_customer_endpoints.py.
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
from app.modules.auth.models import Permission, Role, RolePermission

RO_PERMISSIONS = (
    "repair_order.read",
    "repair_order.create",
    "repair_order.update",
    "repair_order.delete",
    "repair_order.transition",
)


@pytest_asyncio.fixture
async def ro_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    """Extend the shared seeded_db with repair_order permissions on the admin role."""
    role_row = (await seeded_db.execute(
        select(Role).where(Role.code == "admin")
    )).scalar_one()

    for code in RO_PERMISSIONS:
        perm = Permission(
            code=code,
            resource=code.split(".")[0],
            action=".".join(code.split(".")[1:]),
            description="",
        )
        seeded_db.add(perm)
    await seeded_db.flush()

    for code in RO_PERMISSIONS:
        perm_row = (await seeded_db.execute(
            select(Permission).where(Permission.code == code)
        )).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm_row.id))
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def ro_client(
    ro_seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield ro_seeded_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def _login(client: AsyncClient) -> str:
    """Log in as the test admin and return the access token."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Test1234!"},
        headers={"X-Garage-ID": "1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Garage-ID": "1"}


# ---------------------------------------------------------------------------
# POST /repair-orders — create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateRepairOrder:
    async def test_create_minimal(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={
                "customer_id": 999,
                "description": "Engine knock noise",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["actual_cost_minor"] == 0
        assert "id" in body

    async def test_create_with_all_fields(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={
                "customer_id": 1,
                "vehicle_id": None,
                "description": "Full service",
                "priority": "high",
                "estimated_cost_minor": 50000,
                "estimated_cost_currency": "TND",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["priority"] == "high"
        assert body["estimated_cost_minor"] == 50000
        assert body["estimated_cost_currency"] == "TND"

    async def test_create_requires_auth(self, ro_client: AsyncClient):
        resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Test"},
        )
        assert resp.status_code == 401

    async def test_create_invalid_currency_rejected(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={
                "customer_id": 1,
                "description": "Test",
                "estimated_cost_currency": "xxx",  # lowercase — invalid
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /repair-orders — list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListRepairOrders:
    async def test_list_empty(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.get("/api/v1/repair-orders", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_returns_created_ro(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Check brakes"},
            headers=_auth(token),
        )
        resp = await ro_client.get("/api/v1/repair-orders", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_filter_by_status(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "RO 1"},
            headers=_auth(token),
        )
        resp = await ro_client.get(
            "/api/v1/repair-orders?status=created", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_filter_by_nonexistent_status_returns_empty(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.get(
            "/api/v1/repair-orders?status=delivered", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /repair-orders/{id} — detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetRepairOrder:
    async def test_get_existing(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Coolant leak"},
            headers=_auth(token),
        )
        public_id = create_resp.json()["id"]

        resp = await ro_client.get(
            f"/api/v1/repair-orders/{public_id}", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Coolant leak"

    async def test_get_nonexistent_returns_404(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.get(
            "/api/v1/repair-orders/00000000-0000-0000-0000-000000000000",
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /repair-orders/{id} — update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUpdateRepairOrder:
    async def test_update_description(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Original"},
            headers=_auth(token),
        )
        public_id = create_resp.json()["id"]

        resp = await ro_client.patch(
            f"/api/v1/repair-orders/{public_id}?version=1",
            json={"description": "Updated description"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"
        assert resp.json()["version"] == 2

    async def test_stale_version_returns_409(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Test"},
            headers=_auth(token),
        )
        public_id = create_resp.json()["id"]

        resp = await ro_client.patch(
            f"/api/v1/repair-orders/{public_id}?version=99",
            json={"description": "Should fail"},
            headers=_auth(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "stale_version"


# ---------------------------------------------------------------------------
# POST /repair-orders/{id}/status-transition
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStatusTransition:
    async def test_valid_transition_succeeds(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Gear box noise"},
            headers=_auth(token),
        )
        public_id = create_resp.json()["id"]

        resp = await ro_client.post(
            f"/api/v1/repair-orders/{public_id}/status-transition",
            json={"new_status": "diagnosis"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "diagnosis"

    async def test_invalid_transition_returns_409(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Test"},
            headers=_auth(token),
        )
        public_id = create_resp.json()["id"]

        resp = await ro_client.post(
            f"/api/v1/repair-orders/{public_id}/status-transition",
            json={"new_status": "delivered"},
            headers=_auth(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "invalid_transition"

    async def test_full_lifecycle(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Full repair"},
            headers=_auth(token),
        )
        pid = create_resp.json()["id"]

        for new_status in ["diagnosis", "in_repair", "finished", "delivered"]:
            resp = await ro_client.post(
                f"/api/v1/repair-orders/{pid}/status-transition",
                json={"new_status": new_status},
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"Transition to {new_status} failed: {resp.text}"
            assert resp.json()["status"] == new_status


# ---------------------------------------------------------------------------
# POST /repair-orders/{id}/labor-lines
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLaborLines:
    async def test_add_labor_line_updates_cost(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Oil change"},
            headers=_auth(token),
        )
        pid = create_resp.json()["id"]

        resp = await ro_client.post(
            f"/api/v1/repair-orders/{pid}/labor-lines",
            json={"labor_type": "Oil change", "rate_minor": 4000},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        # Labor is a flat price: amount = rate, duration is no longer sent
        assert resp.json()["actual_cost_minor"] == 4000


# ---------------------------------------------------------------------------
# POST /repair-orders/{id}/part-lines
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPartLines:
    async def test_add_part_line_updates_cost(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Replace filter"},
            headers=_auth(token),
        )
        pid = create_resp.json()["id"]

        resp = await ro_client.post(
            f"/api/v1/repair-orders/{pid}/part-lines",
            json={"part_name": "Oil filter", "quantity": 1, "unit_cost_minor": 2500},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["actual_cost_minor"] == 2500


# ---------------------------------------------------------------------------
# DELETE /repair-orders/{id} — soft delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSoftDelete:
    async def test_delete_returns_204(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "To be deleted"},
            headers=_auth(token),
        )
        pid = create_resp.json()["id"]

        resp = await ro_client.delete(
            f"/api/v1/repair-orders/{pid}", headers=_auth(token)
        )
        assert resp.status_code == 204

    async def test_deleted_ro_not_in_list(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        create_resp = await ro_client.post(
            "/api/v1/repair-orders",
            json={"customer_id": 1, "description": "Ghost RO"},
            headers=_auth(token),
        )
        pid = create_resp.json()["id"]
        await ro_client.delete(f"/api/v1/repair-orders/{pid}", headers=_auth(token))

        resp = await ro_client.get("/api/v1/repair-orders", headers=_auth(token))
        ids = [item["id"] for item in resp.json()["items"]]
        assert pid not in ids

    async def test_delete_nonexistent_returns_404(self, ro_client: AsyncClient):
        token = await _login(ro_client)
        resp = await ro_client.delete(
            "/api/v1/repair-orders/00000000-0000-0000-0000-000000000000",
            headers=_auth(token),
        )
        assert resp.status_code == 404
