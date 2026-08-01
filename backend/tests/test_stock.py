"""Tests for Stock movement engine — Issue #25."""
from __future__ import annotations

import time
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission
from app.modules.parts.models import Part, PartStatus
from app.modules.parts.stock_models import StockMovementType
from app.modules.parts.stock_service import (
    NegativeStockError,
    record_movement,
    release_all_for_ref,
    reserve_for_ref,
)
from app.modules.parts.stock_repository import StockRepository

PART_PERMISSIONS = ("part.read", "part.create", "part.update", "part.delete")
RO_PERMISSIONS = (
    "repair_order.read", "repair_order.create", "repair_order.update",
    "repair_order.delete", "repair_order.transition",
)
ALL_PERMISSIONS = PART_PERMISSIONS + RO_PERMISSIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def stock_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    role_row = (await seeded_db.execute(
        select(Role).where(Role.code == "admin")
    )).scalar_one()

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
        perm_row = (await seeded_db.execute(
            select(Permission).where(Permission.code == code)
        )).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm_row.id))
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def stock_client(
    stock_seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield stock_seeded_db

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


async def _create_part(client: AsyncClient, token: str, sku: str = "PART-001") -> dict:
    resp = await client.post(
        "/api/v1/parts",
        json={
            "sku_code": sku,
            "name": f"Test Part {sku}",
            "purchase_price_minor": 1000,
            "selling_price_minor": 1500,
            "reorder_threshold": 5,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_part_db(db: AsyncSession, sku: str = "P-DB-001") -> Part:
    part = Part(
        garage_id=1,
        sku_code=sku,
        name=f"DB Part {sku}",
        purchase_price_minor=1000,
        selling_price_minor=1500,
        reorder_threshold=5,
        unit_of_measure="pcs",
        status=PartStatus.active,
    )
    db.add(part)
    await db.flush()
    return part


async def _create_ro(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/repair-orders",
        json={"customer_id": 1, "description": "Test RO"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _complete_diagnosis(client: AsyncClient, token: str, db: AsyncSession, ro_id: str) -> None:
    """Assign a mechanic, accept the assignment, and complete the diagnosis form —
    the preconditions the diagnosis → in_repair transition now enforces."""
    admin_id = (
        await db.execute(select(AppUser.id).where(AppUser.email == "admin@test.com"))
    ).scalar_one()
    resp = await client.put(
        f"/api/v1/repair-orders/{ro_id}/assign",
        json={"user_id": admin_id},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"/api/v1/repair-orders/{ro_id}/accept-assignment",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    resp = await client.put(
        f"/api/v1/repair-orders/{ro_id}/diagnosis",
        json={
            "answers": {"D1": False, "D2": False, "D3": False, "D4": False, "D5": False},
            "completed": True,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Stock level endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStockLevel:
    async def test_get_stock_level_zero_for_new_part(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="SL-001")
        resp = await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["on_hand"] == 0
        assert data["reserved"] == 0
        assert data["available"] == 0

    async def test_get_stock_level_unknown_part_404(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        resp = await stock_client.get(
            f"/api/v1/parts/{uuid.uuid4()}/stock", headers=_auth(token)
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Movement tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStockMovements:
    async def test_in_movement_increases_on_hand(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="IN-001")
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 100, "unit_cost_minor": 1000, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        # Verify level updated
        level = await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )
        assert level.json()["on_hand"] == 100

    async def test_out_movement_decreases_on_hand(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="OUT-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 50, "unit_cost_minor": 1000, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 20},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        level = await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )
        assert level.json()["on_hand"] == 30

    async def test_adjustment_positive(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="ADJ-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "adjustment", "quantity": 5, "reason": "Inventory count"},
            headers=_auth(token),
        )
        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert level["on_hand"] == 15

    async def test_adjustment_negative(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="ADJ-002")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "adjustment", "quantity": -3, "reason": "Shrinkage"},
            headers=_auth(token),
        )
        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert level["on_hand"] == 7

    async def test_list_movements(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="LIST-M-001")
        for i in range(3):
            await stock_client.post(
                f"/api/v1/parts/{part['id']}/stock/movements",
                json={"type": "in", "quantity": 10, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
                headers=_auth(token),
            )
        resp = await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock/movements", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_weighted_average_cost(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="WAC-001")
        # Buy 10 @ 1000
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 1000, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        # Buy 10 @ 2000 → avg = (10*1000 + 10*2000) / 20 = 1500
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 2000, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert level["avg_cost_minor"] == 1500
        assert level["on_hand"] == 20

    async def test_requires_auth(self, stock_client: AsyncClient):
        resp = await stock_client.get(f"/api/v1/parts/{uuid.uuid4()}/stock")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Negative stock tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNegativeStock:
    async def test_out_beyond_available_returns_409(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="NEG-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 15},
            headers=_auth(token),
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == "negative_stock"
        assert detail["available"] == 10
        assert detail["requested"] == 15

    async def test_out_zero_stock_returns_409(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="NEG-002")
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 1},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    async def test_override_allows_negative(self, stock_seeded_db: AsyncSession):
        part = await _create_part_db(stock_seeded_db, sku="NEG-OVR-001")
        await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.in_,
            quantity=5, unit_cost_minor=100,
        )
        # Override: allow negative
        mv = await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.out,
            quantity=10,
            reason="Emergency override",
            allow_negative=True,
        )
        assert mv is not None
        level = await StockRepository.get_level(stock_seeded_db, 1, part.id)
        assert level.on_hand == -5


# ---------------------------------------------------------------------------
# Reservation flow tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestReservationFlow:
    async def test_reserve_increases_reserved(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="RES-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 20, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/reserve",
            json={"quantity": 5, "ref_type": "repair_order", "ref_id": "ro-123"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert level["reserved"] == 5
        assert level["available"] == 15

    async def test_release_decreases_reserved(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="REL-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 20, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/reserve",
            json={"quantity": 8, "ref_type": "repair_order", "ref_id": "ro-456"},
            headers=_auth(token),
        )
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/release",
            json={"quantity": 8, "ref_type": "repair_order", "ref_id": "ro-456"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert level["reserved"] == 0

    async def test_out_respects_reserved(self, stock_client: AsyncClient):
        """Out movement should consider reserved qty when checking availability."""
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="RES-OUT-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        # Reserve 8 → available = 2
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/reserve",
            json={"quantity": 8, "ref_type": "repair_order", "ref_id": "ro-789"},
            headers=_auth(token),
        )
        # Try to take 5 → should fail (only 2 available)
        resp = await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 5},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    async def test_release_all_for_ref_at_service_layer(
        self, stock_seeded_db: AsyncSession
    ):
        part = await _create_part_db(stock_seeded_db, sku="RELALL-001")
        await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.in_, quantity=50, unit_cost_minor=200,
        )
        ro_ref = str(uuid.uuid4())
        await reserve_for_ref(
            stock_seeded_db, garage_id=1, part_id=part.id,
            quantity=10, ref_type="repair_order", ref_id=ro_ref,
        )
        level = await StockRepository.get_level(stock_seeded_db, 1, part.id)
        assert level.reserved == 10

        released = await release_all_for_ref(
            stock_seeded_db, garage_id=1,
            ref_type="repair_order", ref_id=ro_ref,
        )
        assert len(released) == 1
        level = await StockRepository.get_level(stock_seeded_db, 1, part.id)
        assert level.reserved == 0

    async def test_release_all_is_atomic_with_ro_cancellation(
        self, stock_client: AsyncClient
    ):
        """Cancelling an RO releases all its stock reservations in the same tx."""
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="ATOM-001")

        # Add stock
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 20, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        # Create an RO
        ro_id = await _create_ro(stock_client, token)

        # Reserve parts for this RO
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/reserve",
            json={"quantity": 7, "ref_type": "repair_order", "ref_id": ro_id},
            headers=_auth(token),
        )
        before = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert before["reserved"] == 7

        # Cancel (soft-delete) the RO
        del_resp = await stock_client.delete(
            f"/api/v1/repair-orders/{ro_id}", headers=_auth(token)
        )
        assert del_resp.status_code == 204

        # Reservation must be released atomically
        after = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert after["reserved"] == 0


# ---------------------------------------------------------------------------
# Low-stock alerts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLowStockAlerts:
    async def test_alert_created_below_threshold(self, stock_seeded_db: AsyncSession):
        part = await _create_part_db(stock_seeded_db, sku="ALERT-001")
        # Seed stock above threshold
        await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.in_, quantity=10, unit_cost_minor=200,
        )
        # Take stock down to threshold (threshold is 5)
        await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.out, quantity=5,
        )
        # on_hand == 5 == threshold → alert
        alerts = await StockRepository.list_alerts(stock_seeded_db, garage_id=1)
        assert any(a.part_id == part.id for a in alerts)

    async def test_alert_endpoint(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="ALRT-API-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 5},
            headers=_auth(token),
        )
        resp = await stock_client.get("/api/v1/stock/alerts", headers=_auth(token))
        assert resp.status_code == 200
        ids = [a["part_id"] for a in resp.json()]
        # part_id is the internal int, we just check there is at least one alert
        assert len(resp.json()) >= 1

    async def test_acknowledge_alert(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="ACK-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 5, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 1},
            headers=_auth(token),
        )
        alerts = (await stock_client.get(
            "/api/v1/stock/alerts", headers=_auth(token)
        )).json()
        assert len(alerts) >= 1
        alert_id = alerts[0]["id"]

        resp = await stock_client.post(
            f"/api/v1/stock/alerts/{alert_id}/acknowledge",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"


# ---------------------------------------------------------------------------
# Load test: 1000 movements < 10s
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLoadPerformance:
    async def test_1000_movements_under_10s(self, stock_seeded_db: AsyncSession):
        """Process 1 000 in-movements at the service layer and assert < 10 s."""
        part = await _create_part_db(stock_seeded_db, sku="LOAD-001")
        part_id = part.id

        start = time.monotonic()
        for i in range(1000):
            await record_movement(
                stock_seeded_db,
                garage_id=1,
                part_id=part_id,
                movement_type=StockMovementType.in_,
                quantity=1,
                unit_cost_minor=100,
            )
        elapsed = time.monotonic() - start

        level = await StockRepository.get_level(stock_seeded_db, 1, part_id)
        assert level.on_hand == 1000
        assert elapsed < 10.0, f"Load test too slow: {elapsed:.2f}s for 1000 movements"


# ---------------------------------------------------------------------------
# Alert status lifecycle (open → acknowledged → resolved)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAlertStatusLifecycle:
    async def _trigger_alert(self, client: AsyncClient, token: str, sku: str) -> dict:
        part = await _create_part(client, token, sku=sku)
        await client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 5, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        # Drive stock to threshold (5 → 5 == threshold)
        await client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "out", "quantity": 1},
            headers=_auth(token),
        )
        alerts = (await client.get("/api/v1/stock/alerts", headers=_auth(token))).json()
        assert any(a["status"] == "open" for a in alerts)
        return next(a for a in alerts if a["status"] == "open")

    async def test_new_alert_has_open_status(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        alert = await self._trigger_alert(stock_client, token, sku="ST-OPEN-001")
        assert alert["status"] == "open"

    async def test_acknowledge_sets_status(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        alert = await self._trigger_alert(stock_client, token, sku="ST-ACK-001")
        resp = await stock_client.post(
            f"/api/v1/stock/alerts/{alert['id']}/acknowledge",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"

    async def test_resolve_sets_status(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        alert = await self._trigger_alert(stock_client, token, sku="ST-RES-001")
        resp = await stock_client.post(
            f"/api/v1/stock/alerts/{alert['id']}/resolve",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_resolved_excluded_from_default_list(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        alert = await self._trigger_alert(stock_client, token, sku="ST-EXCL-001")
        await stock_client.post(
            f"/api/v1/stock/alerts/{alert['id']}/resolve", headers=_auth(token)
        )
        open_alerts = (await stock_client.get(
            "/api/v1/stock/alerts", headers=_auth(token)
        )).json()
        assert all(a["id"] != alert["id"] for a in open_alerts)

    async def test_filter_by_status(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        await self._trigger_alert(stock_client, token, sku="ST-FILT-001")
        resp = await stock_client.get(
            "/api/v1/stock/alerts?status=open", headers=_auth(token)
        )
        assert resp.status_code == 200
        assert all(a["status"] == "open" for a in resp.json())

    async def test_alert_has_suggested_fields(self, stock_seeded_db: AsyncSession):
        part = await _create_part_db(stock_seeded_db, sku="ST-SUGG-001")
        part.supplier_hint_id = 42
        part.reorder_quantity = 20
        await stock_seeded_db.flush()

        await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.in_, quantity=5, unit_cost_minor=100,
        )
        await record_movement(
            stock_seeded_db, garage_id=1, part_id=part.id,
            movement_type=StockMovementType.out, quantity=1,
        )
        alerts = await StockRepository.list_alerts(stock_seeded_db, garage_id=1)
        alert = next((a for a in alerts if a.part_id == part.id), None)
        assert alert is not None
        assert alert.suggested_supplier_id == 42
        assert alert.suggested_reorder_quantity == 20


# ---------------------------------------------------------------------------
# Stock valuation report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStockValuation:
    async def test_valuation_empty(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        resp = await stock_client.get("/api/v1/stock/valuation", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total_inventory_value_minor" in data

    async def test_valuation_calculates_correctly(self, stock_client: AsyncClient):
        token = await _login(stock_client)
        part = await _create_part(stock_client, token, sku="VAL-001")
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 10, "unit_cost_minor": 2000, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        resp = await stock_client.get("/api/v1/stock/valuation", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        matched = next((i for i in data["items"] if i["on_hand"] == 10 and i["avg_cost_minor"] == 2000), None)
        assert matched is not None
        assert matched["total_value_minor"] == 20000


# ---------------------------------------------------------------------------
# RO stock integration: provisional reservation + in_repair commit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestROStockIntegration:
    async def _setup(self, client: AsyncClient, token: str, sku: str = "RO-INT-001"):
        """Create a part with stock and return (part, ro_id)."""
        part = await _create_part(client, token, sku=sku)
        # Get the internal part id from stock level endpoint
        # We need the internal integer id — create a movement first so we can read it
        await client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 20, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        ro_id = await _create_ro(client, token)
        return part, ro_id

    async def test_add_part_line_with_part_id_creates_reservation(
        self, stock_client: AsyncClient, stock_seeded_db: AsyncSession
    ):
        token = await _login(stock_client)
        sku = "RO-RES-001"
        part = await _create_part(stock_client, token, sku=sku)
        # Add stock via HTTP so stock_level row is created
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 20, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        ro_id = await _create_ro(stock_client, token)

        # Add part line with part_id — should reserve 3 units
        resp = await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/part-lines",
            json={
                "part_name": "Test Part",
                "quantity": 3,
                "unit_cost_minor": 500,
                "part_public_id": part["id"],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200

        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        assert level["reserved"] == 3
        assert level["available"] == 17

    async def test_in_repair_transition_commits_reservations(
        self, stock_client: AsyncClient, stock_seeded_db: AsyncSession
    ):
        token = await _login(stock_client)
        sku = "RO-COMMIT-001"
        part = await _create_part(stock_client, token, sku=sku)
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 20, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        ro_id = await _create_ro(stock_client, token)

        # Add catalog-linked part line → reservation
        await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/part-lines",
            json={
                "part_name": "Test Part",
                "quantity": 5,
                "unit_cost_minor": 500,
                "part_public_id": part["id"],
            },
            headers=_auth(token),
        )

        # Transition to diagnosis first (required by state machine)
        await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/status-transition",
            json={"new_status": "diagnosis"},
            headers=_auth(token),
        )
        await _complete_diagnosis(stock_client, token, stock_seeded_db, ro_id)
        # Transition to in_repair → should commit the reservation
        resp = await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/status-transition",
            json={"new_status": "in_repair"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

        level = (await stock_client.get(
            f"/api/v1/parts/{part['id']}/stock", headers=_auth(token)
        )).json()
        # After commit: on_hand reduced, reserved back to 0
        assert level["on_hand"] == 15
        assert level["reserved"] == 0

    async def test_commit_fails_if_stock_depleted(
        self, stock_client: AsyncClient, stock_seeded_db: AsyncSession
    ):
        """If stock was consumed between reservation and in_repair, 409 is returned."""
        token = await _login(stock_client)
        sku = "RO-FAIL-001"
        part = await _create_part(stock_client, token, sku=sku)
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "in", "quantity": 5, "unit_cost_minor": 500, "ref_type": "purchase_order", "ref_id": "test-seed"},
            headers=_auth(token),
        )
        ro_id = await _create_ro(stock_client, token)
        # Reserve 5 units
        await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/part-lines",
            json={
                "part_name": "Test Part",
                "quantity": 5,
                "unit_cost_minor": 500,
                "part_public_id": part["id"],
            },
            headers=_auth(token),
        )
        # Drain stock via manual adjustment (simulating external depletion)
        # We need to work around: reserved=5, on_hand=5, available=0
        # The commit releases reservation first so available becomes 5, then out(5) succeeds
        # To force failure: reduce on_hand below 5 via adjustment
        await stock_client.post(
            f"/api/v1/parts/{part['id']}/stock/movements",
            json={"type": "adjustment", "quantity": -5, "reason": "External loss"},
            headers=_auth(token),
        )
        # Now on_hand=0, reserved=5, available=-5 → commit should fail
        await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/status-transition",
            json={"new_status": "diagnosis"},
            headers=_auth(token),
        )
        await _complete_diagnosis(stock_client, token, stock_seeded_db, ro_id)
        resp = await stock_client.post(
            f"/api/v1/repair-orders/{ro_id}/status-transition",
            json={"new_status": "in_repair"},
            headers=_auth(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "negative_stock_on_commit"
