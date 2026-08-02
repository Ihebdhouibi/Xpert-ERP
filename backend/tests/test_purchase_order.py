"""Tests for Purchase Order flow — Issue #37."""
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

PO_PERMISSIONS = (
    "purchase_order.read",
    "purchase_order.create",
    "purchase_order.send",
    "purchase_order.reception.record",
)
PART_PERMISSIONS = ("part.read", "part.create", "part.update", "part.delete")
SUPPLIER_PERMISSIONS = ("supplier.read", "supplier.create", "supplier.update", "supplier.delete")
STOCK_PERMISSIONS = ("part.update",)

ALL_PERMISSIONS = PO_PERMISSIONS + PART_PERMISSIONS + SUPPLIER_PERMISSIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def po_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
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
async def po_client(
    po_seeded_db: AsyncSession, mock_redis
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield po_seeded_db

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


async def _create_supplier(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/suppliers",
        json={"name": "Test Supplier"},
        headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_part(client: AsyncClient, token: str, sku: str = "SKU-001") -> str:
    resp = await client.post(
        "/api/v1/parts",
        json={
            "sku_code": sku,
            "name": f"Test Part {sku}",
            "unit_of_measure": "pcs",
            "purchase_price_minor": 1000,
            "selling_price_minor": 1500,
        },
        headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests: CRUD
# ---------------------------------------------------------------------------


class TestPOCreate:
    async def test_create_po(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token)

        resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "expected_delivery_date": "2026-06-30",
                "lines": [
                    {"part_public_id": part_id, "quantity_ordered": 10, "unit_price_ht": 2500}
                ],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "draft"
        assert data["doc_number"].startswith("PO-")
        assert len(data["lines"]) == 1
        assert data["lines"][0]["quantity_ordered"] == 10
        assert data["lines"][0]["unit_price_ht"] == 2500
        assert data["total_ht"] == 25000

    async def test_create_po_missing_supplier(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        part_id = await _create_part(po_client, token)

        resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": "00000000-0000-0000-0000-000000000000",
                "lines": [
                    {"part_public_id": part_id, "quantity_ordered": 5, "unit_price_ht": 1000}
                ],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 404

    async def test_create_po_no_lines_rejected(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)

        resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={"supplier_public_id": supplier_id, "lines": []},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 422


class TestPOList:
    async def test_list_returns_items(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token)

        # Create two POs
        for _ in range(2):
            await po_client.post(
                "/api/v1/purchase-orders",
                json={
                    "supplier_public_id": supplier_id,
                    "lines": [{"part_public_id": part_id, "quantity_ordered": 1, "unit_price_ht": 500}],
                },
                headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
            )

        resp = await po_client.get(
            "/api/v1/purchase-orders",
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_filter_by_status(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token)

        create_resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": 1, "unit_price_ht": 500}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        po_id = create_resp.json()["id"]
        version = create_resp.json()["version"]

        # Send it
        await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )

        # Filter by sent
        resp = await po_client.get(
            "/api/v1/purchase-orders?status=sent",
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        # Filter by draft returns 0
        resp2 = await po_client.get(
            "/api/v1/purchase-orders?status=draft",
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp2.json()["total"] == 0


# ---------------------------------------------------------------------------
# Tests: Status transitions
# ---------------------------------------------------------------------------


class TestPOTransitions:
    async def _setup_draft_po(self, client: AsyncClient, token: str) -> tuple[str, int]:
        supplier_id = await _create_supplier(client, token)
        part_id = await _create_part(client, token, sku="SKU-T01")
        resp = await client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": 5, "unit_price_ht": 1000}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        data = resp.json()
        return data["id"], data["version"]

    async def test_send_draft_po(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, version = await self._setup_draft_po(po_client, token)

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"

    async def test_send_non_draft_fails(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, version = await self._setup_draft_po(po_client, token)

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        new_version = resp.json()["version"]

        resp2 = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": new_version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp2.status_code == 422

    async def test_cancel_sent_po(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, version = await self._setup_draft_po(po_client, token)

        send_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        new_version = send_resp.json()["version"]

        cancel_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/cancel",
            json={"version": new_version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

    async def test_cancel_completed_fails(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token, sku="SKU-T02")

        create_resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": 2, "unit_price_ht": 500}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        po_id = create_resp.json()["id"]
        line_id = create_resp.json()["lines"][0]["id"]
        version = create_resp.json()["version"]

        send_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        version = send_resp.json()["version"]

        receive_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 2}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert receive_resp.json()["status"] == "completed"
        version = receive_resp.json()["version"]

        cancel_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/cancel",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert cancel_resp.status_code == 422

    async def test_version_conflict(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, version = await self._setup_draft_po(po_client, token)

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version + 99},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "version_conflict"


# ---------------------------------------------------------------------------
# Tests: Reception flow + stock movements
# ---------------------------------------------------------------------------


class TestPOReception:
    async def _setup_sent_po(
        self, client: AsyncClient, token: str, qty: int = 10
    ) -> tuple[str, int, int, str]:
        supplier_id = await _create_supplier(client, token)
        part_id = await _create_part(client, token, sku="SKU-R01")

        create_resp = await client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": qty, "unit_price_ht": 3000}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        po_id = create_resp.json()["id"]
        line_id = create_resp.json()["lines"][0]["id"]
        version = create_resp.json()["version"]

        send_resp = await client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        version = send_resp.json()["version"]
        return po_id, line_id, version, part_id

    async def test_full_reception_creates_stock_movement(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, line_id, version, part_id = await self._setup_sent_po(po_client, token, qty=5)

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 5}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        assert data["lines"][0]["quantity_received"] == 5
        assert data["lines"][0]["match_flag"] == "ok"

        # Verify stock level updated
        stock_resp = await po_client.get(
            f"/api/v1/parts/{part_id}/stock",
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert stock_resp.status_code == 200
        assert stock_resp.json()["on_hand"] == 5

    async def test_partial_reception_sets_partially_received(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, line_id, version, part_id = await self._setup_sent_po(po_client, token, qty=10)

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 6}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "partially_received"
        assert data["lines"][0]["quantity_received"] == 6
        # 6/10 = 40% discrepancy > 5% tolerance
        assert data["lines"][0]["match_flag"] == "qty_mismatch"

    async def test_reception_on_draft_implicitly_sends_po(self, po_client: AsyncClient) -> None:
        """Receiving straight off a draft PO is allowed: sending is not a
        formal step in this garage's workflow, so the draft is implicitly
        marked 'sent' before the reception is recorded."""
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token, sku="SKU-R02")

        create_resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": 3, "unit_price_ht": 1000}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert create_resp.json()["status"] == "draft"
        po_id = create_resp.json()["id"]
        line_id = create_resp.json()["lines"][0]["id"]
        version = create_resp.json()["version"]

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 3}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "completed"
        assert data["lines"][0]["quantity_received"] == 3

    async def test_reception_on_cancelled_po_fails(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, line_id, version, _ = await self._setup_sent_po(po_client, token, qty=3)

        cancel_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/cancel",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        cancelled_version = cancel_resp.json()["version"]

        resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": cancelled_version, "lines": [{"line_id": line_id, "quantity_received": 3}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp.status_code == 422

    async def test_multi_reception_accumulates(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        po_id, line_id, version, part_id = await self._setup_sent_po(po_client, token, qty=10)

        # First partial
        resp1 = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 4}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp1.json()["status"] == "partially_received"
        version = resp1.json()["version"]

        # Second to complete
        resp2 = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 6}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert resp2.json()["status"] == "completed"
        assert resp2.json()["lines"][0]["quantity_received"] == 10
        assert resp2.json()["lines"][0]["match_flag"] == "ok"

        # Stock should have 10
        stock = await po_client.get(
            f"/api/v1/parts/{part_id}/stock",
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert stock.json()["on_hand"] == 10


# ---------------------------------------------------------------------------
# Tests: Three-way match
# ---------------------------------------------------------------------------


class TestThreeWayMatch:
    async def test_invoiced_within_tolerance_ok(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token, sku="SKU-M01")

        create_resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": 10, "unit_price_ht": 1000}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        po_id = create_resp.json()["id"]
        line_id = create_resp.json()["lines"][0]["id"]
        version = create_resp.json()["version"]

        send_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        version = send_resp.json()["version"]

        # Receive all 10
        recv_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 10}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        version = recv_resp.json()["version"]

        # Invoice 10 (exact match)
        inv_resp = await po_client.patch(
            f"/api/v1/purchase-orders/{po_id}/lines/{line_id}/invoice",
            json={"quantity_invoiced": 10},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert inv_resp.status_code == 200
        assert inv_resp.json()["match_flag"] == "ok"

    async def test_invoiced_outside_tolerance_flagged(self, po_client: AsyncClient) -> None:
        token = await _login(po_client)
        supplier_id = await _create_supplier(po_client, token)
        part_id = await _create_part(po_client, token, sku="SKU-M02")

        create_resp = await po_client.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_public_id": supplier_id,
                "lines": [{"part_public_id": part_id, "quantity_ordered": 10, "unit_price_ht": 1000}],
            },
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        po_id = create_resp.json()["id"]
        line_id = create_resp.json()["lines"][0]["id"]
        version = create_resp.json()["version"]

        send_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/send",
            json={"version": version},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        version = send_resp.json()["version"]

        # Receive 10
        recv_resp = await po_client.post(
            f"/api/v1/purchase-orders/{po_id}/receive",
            json={"version": version, "lines": [{"line_id": line_id, "quantity_received": 10}]},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        version = recv_resp.json()["version"]

        # Invoice only 8 (20% discrepancy > 5% tolerance)
        inv_resp = await po_client.patch(
            f"/api/v1/purchase-orders/{po_id}/lines/{line_id}/invoice",
            json={"quantity_invoiced": 8},
            headers={"Authorization": f"Bearer {token}", "X-Garage-ID": "1"},
        )
        assert inv_resp.status_code == 200
        assert inv_resp.json()["match_flag"] == "inv_mismatch"
