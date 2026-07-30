"""Tests for Supplier Invoice + Three-Way Match — Issue #38."""
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

SI_PERMISSIONS = (
    "supplier_invoice.read",
    "supplier_invoice.create",
    "supplier_invoice.post",
    "supplier_invoice.approve",
    "supplier_invoice.override",
)
PO_PERMISSIONS = (
    "purchase_order.read",
    "purchase_order.create",
    "purchase_order.send",
    "purchase_order.reception.record",
)
PART_PERMISSIONS = ("part.read", "part.create", "part.update", "part.delete")
SUPPLIER_PERMISSIONS = ("supplier.read", "supplier.create", "supplier.update", "supplier.delete")

ALL_PERMISSIONS = SI_PERMISSIONS + PO_PERMISSIONS + PART_PERMISSIONS + SUPPLIER_PERMISSIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def si_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
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
async def si_client(
    si_seeded_db: AsyncSession, mock_redis
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield si_seeded_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HEADERS = {"X-Garage-ID": "1"}


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Test1234!"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **HEADERS}


async def _create_supplier(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/suppliers",
        json={"name": "Test Supplier SI"},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_part(client: AsyncClient, token: str, sku: str = "SKU-SI-001") -> str:
    resp = await client.post(
        "/api/v1/parts",
        json={
            "sku_code": sku,
            "name": f"Part {sku}",
            "unit_of_measure": "pcs",
            "purchase_price_minor": 1000,
            "selling_price_minor": 1500,
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_and_receive_po(
    client: AsyncClient,
    token: str,
    supplier_id: str,
    part_id: str,
    qty_ordered: int = 10,
    qty_received: int = 10,
    unit_price: int = 2500,
) -> tuple[str, int]:
    """Returns (po_public_id, po_line_id)."""
    # Create
    resp = await client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_public_id": supplier_id,
            "lines": [{"part_public_id": part_id, "quantity_ordered": qty_ordered, "unit_price_ht": unit_price}],
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    po = resp.json()
    po_id = po["id"]
    line_id = po["lines"][0]["id"]

    # Send
    resp = await client.post(
        f"/api/v1/purchase-orders/{po_id}/send",
        json={"version": po["version"]},
        headers=auth(token),
    )
    assert resp.status_code == 200, resp.text

    # Receive
    resp = await client.post(
        f"/api/v1/purchase-orders/{po_id}/receive",
        json={
            "version": resp.json()["version"],
            "lines": [{"line_id": line_id, "quantity_received": qty_received}],
        },
        headers=auth(token),
    )
    assert resp.status_code == 200, resp.text
    return po_id, line_id


# ---------------------------------------------------------------------------
# Tests: Create
# ---------------------------------------------------------------------------


class TestSICreate:
    async def test_create_si_draft(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token)
        po_id, line_id = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-2026-001",
                "lines": [
                    {"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500, "vat_rate": 20.0}
                ],
                "received_at": "2026-05-28T10:00:00",
                "due_date": "2026-06-28",
            },
            headers=auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "draft"
        assert data["number"] == "INV-2026-001"
        assert data["has_discrepancy"] is False
        assert len(data["lines"]) == 1
        assert data["lines"][0]["quantity"] == 10
        assert data["lines"][0]["line_total_ht"] == 25000
        assert data["lines"][0]["line_total_ttc"] == 30000

    async def test_create_si_missing_supplier(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-SI-002")
        po_id, line_id = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": "00000000-0000-0000-0000-000000000000",
                "po_public_id": po_id,
                "number": "INV-X",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        assert resp.status_code == 404

    async def test_create_si_missing_po(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": "00000000-0000-0000-0000-000000000000",
                "number": "INV-X",
                "lines": [{"po_line_id": 999, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        assert resp.status_code == 404

    async def test_create_si_no_lines_rejected(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-SI-003")
        po_id, _ = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-X",
                "lines": [],
            },
            headers=auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: List
# ---------------------------------------------------------------------------


class TestSIList:
    async def test_list_returns_items(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-LIST-001")
        po_id, line_id = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        for i in range(2):
            await si_client.post(
                "/api/v1/supplier-invoices",
                json={
                    "supplier_public_id": supplier_id,
                    "po_public_id": po_id,
                    "number": f"INV-L-{i}",
                    "lines": [{"po_line_id": line_id, "quantity": 5, "unit_price_ht": 2500}],
                },
                headers=auth(token),
            )

        resp = await si_client.get(
            "/api/v1/supplier-invoices",
            headers=auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2


# ---------------------------------------------------------------------------
# Tests: Post (three-way match)
# ---------------------------------------------------------------------------


class TestSIPost:
    async def test_post_no_discrepancy(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-POST-OK")
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=10, qty_received=10, unit_price=2500
        )

        # Create invoice matching exactly
        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-POST-OK",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        assert resp.status_code == 201
        si = resp.json()

        # Post (run three-way match)
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "posted"
        assert data["has_discrepancy"] is False
        assert data["lines"][0]["match_status"] == "ok"

    async def test_post_qty_mismatch_flagged(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-POST-QTY")
        # PO receives 8 out of 10 ordered
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=10, qty_received=8, unit_price=2500
        )

        # Invoice claims 10 (but only 8 were received)
        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-QTY-MISMATCH",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        assert resp.status_code == 201
        si = resp.json()

        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "posted"
        assert data["has_discrepancy"] is True
        assert data["lines"][0]["match_status"] == "qty_mismatch"

    async def test_post_price_mismatch_flagged(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-POST-PRICE")
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=10, qty_received=10, unit_price=2500
        )

        # Invoice has significantly different price (3000 vs 2500 = 20% diff)
        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-PRICE-MISMATCH",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 3000}],
            },
            headers=auth(token),
        )
        assert resp.status_code == 201
        si = resp.json()

        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "posted"
        assert data["has_discrepancy"] is True
        assert data["lines"][0]["match_status"] == "price_mismatch"

    async def test_post_only_from_draft(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-POST-TWICE")
        po_id, line_id = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-TWICE",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()

        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        posted = (await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}", headers=auth(token)
        )).json()

        # Posting again should fail
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": posted["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Override
# ---------------------------------------------------------------------------


class TestSIOverride:
    async def _create_posted_mismatch_si(self, client: AsyncClient, token: str) -> dict:
        supplier_id = await _create_supplier(client, token)
        part_id = await _create_part(client, token, "SKU-OVR")
        po_id, line_id = await _create_and_receive_po(
            client, token, supplier_id, part_id, qty_ordered=10, qty_received=8
        )
        resp = await client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-OVR",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()
        resp = await client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        return resp.json()

    async def test_override_requires_reason(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        si = await self._create_posted_mismatch_si(si_client, token)

        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/override",
            json={"version": si["version"], "reason": ""},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_override_success(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        si = await self._create_posted_mismatch_si(si_client, token)

        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/override",
            json={"version": si["version"], "reason": "Supplier confirmed partial delivery acceptable"},
            headers=auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["override_reason"] == "Supplier confirmed partial delivery acceptable"
        assert data["has_discrepancy"] is True

    async def test_override_no_discrepancy_rejected(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-OVR-NODIFF")
        po_id, line_id = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-NO-DIFF",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()
        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        posted = (await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}", headers=auth(token)
        )).json()

        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/override",
            json={"version": posted["version"], "reason": "Should not work"},
            headers=auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Approve + Mark Paid
# ---------------------------------------------------------------------------


class TestSIApprove:
    async def test_approve_blocks_if_discrepancy_no_override(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-APR-BLOCK")
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=10, qty_received=8
        )
        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-APR-BLOCK",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()
        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        posted = (await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}", headers=auth(token)
        )).json()

        # Attempt to approve without override → 422
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/approve",
            json={"version": posted["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 422

    async def test_approve_after_override_succeeds(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-APR-OVR")
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=10, qty_received=8
        )
        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-APR-OVR",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()
        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        posted = (await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}", headers=auth(token)
        )).json()
        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/override",
            json={"version": posted["version"], "reason": "Accepted"},
            headers=auth(token),
        )
        overridden = (await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}", headers=auth(token)
        )).json()

        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/approve",
            json={"version": overridden["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Tests: Full workflow
# ---------------------------------------------------------------------------


class TestSIFullWorkflow:
    async def test_happy_path_no_discrepancy(self, si_client: AsyncClient) -> None:
        """draft → post (matched) → approve → mark-paid."""
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-WF-OK")
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=5, qty_received=5, unit_price=1000
        )

        # Create
        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-WF-OK",
                "lines": [{"po_line_id": line_id, "quantity": 5, "unit_price_ht": 1000, "vat_rate": 20.0}],
                "received_at": "2026-05-28T10:00:00",
                "due_date": "2026-06-28",
            },
            headers=auth(token),
        )
        assert resp.status_code == 201
        si = resp.json()
        assert si["status"] == "draft"
        assert si["total_ht"] == 5000
        assert si["total_ttc"] == 6000

        # Post
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200
        si = resp.json()
        assert si["status"] == "posted"
        assert si["has_discrepancy"] is False

        # Approve
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/approve",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200
        si = resp.json()
        assert si["status"] == "approved"

        # Mark paid
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/mark-paid",
            json={"version": si["version"], "payment_method": "cash"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

    async def test_workflow_with_discrepancy_and_override(self, si_client: AsyncClient) -> None:
        """draft → post (mismatch) → override → approve → paid."""
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-WF-DISC")
        po_id, line_id = await _create_and_receive_po(
            si_client, token, supplier_id, part_id, qty_ordered=10, qty_received=8, unit_price=2500
        )

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-WF-DISC",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()

        # Post reveals discrepancy
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200
        si = resp.json()
        assert si["has_discrepancy"] is True
        assert si["lines"][0]["match_status"] == "qty_mismatch"

        # Direct approve is blocked
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/approve",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 422

        # Override with reason
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/override",
            json={"version": si["version"], "reason": "Supplier billed for ordered qty, not received"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        si = resp.json()
        assert si["override_reason"] == "Supplier billed for ordered qty, not received"

        # Now approve succeeds
        resp = await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/approve",
            json={"version": si["version"]},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_accounting_export_only_for_approved(self, si_client: AsyncClient) -> None:
        token = await _login(si_client)
        supplier_id = await _create_supplier(si_client, token)
        part_id = await _create_part(si_client, token, "SKU-ACC")
        po_id, line_id = await _create_and_receive_po(si_client, token, supplier_id, part_id)

        resp = await si_client.post(
            "/api/v1/supplier-invoices",
            json={
                "supplier_public_id": supplier_id,
                "po_public_id": po_id,
                "number": "INV-ACC",
                "lines": [{"po_line_id": line_id, "quantity": 10, "unit_price_ht": 2500}],
            },
            headers=auth(token),
        )
        si = resp.json()

        # Draft → export blocked
        resp = await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}/accounting-export",
            headers=auth(token),
        )
        assert resp.status_code == 422

        # Post + approve
        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/post",
            json={"version": si["version"]},
            headers=auth(token),
        )
        posted = (await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}", headers=auth(token)
        )).json()
        await si_client.post(
            f"/api/v1/supplier-invoices/{si['id']}/approve",
            json={"version": posted["version"]},
            headers=auth(token),
        )

        # Now export is available
        resp = await si_client.get(
            f"/api/v1/supplier-invoices/{si['id']}/accounting-export",
            headers=auth(token),
        )
        assert resp.status_code == 200, resp.text
        export = resp.json()
        assert export["journal"] == "purchases"
        assert export["invoice_number"] == "INV-ACC"
        assert len(export["entries"]) == 3
        # Debit 607 = total_ht
        debit_607 = next(e for e in export["entries"] if e["account"] == "607")
        assert debit_607["debit"] == 25000
        # Credit 401 = total_ttc
        credit_401 = next(e for e in export["entries"] if e["account"] == "401")
        assert credit_401["credit"] == 30000
