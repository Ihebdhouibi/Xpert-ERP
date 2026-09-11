"""Tests for Issue #46 — Accounting Export (M10).

Covers:
- Preview endpoint counts pending / already-exported records
- Export creation: marks records as exported, returns completed status
- Re-export: only unexported records included in subsequent export
- Lock: exported invoice cannot be cancelled
- Lock: exported payment cannot be refunded
- Formatters: generic_csv / sage / cegid produce valid ZIP with correct content
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
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
from app.modules.auth.models import Permission, Role, RolePermission
from app.modules.accounting_export.formatters import generate_zip
from app.modules.customer.models import Customer, CustomerStatus, CustomerType

# ---------------------------------------------------------------------------
# Permissions needed by the tests
# ---------------------------------------------------------------------------

_ALL_PERMS = (
    "accounting_export.read",
    "accounting_export.create",
    "accounting_export.download",
    "invoice.read",
    "invoice.create",
    "invoice.update",
    "invoice.delete",
    "invoice.issue",
    "invoice.pay",
    "invoice.cancel",
    "payment.record",
    "credit_note.create",
    "credit_note.read",
    "credit_note.issue",
    "credit_note.void",
    "refund.execute",
    "refund.read",
    "customer.read",
    "customer.create",
    "customer.update",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ae_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    """Extends shared seeded_db with accounting-export permissions + a seeded customer."""
    role_row = (
        await seeded_db.execute(select(Role).where(Role.code == "admin"))
    ).scalar_one()

    for code in _ALL_PERMS:
        perm = Permission(
            code=code,
            resource=code.split(".")[0],
            action=".".join(code.split(".")[1:]),
            description="",
        )
        seeded_db.add(perm)
    await seeded_db.flush()

    for code in _ALL_PERMS:
        perm_row = (
            await seeded_db.execute(select(Permission).where(Permission.code == code))
        ).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm_row.id))

    # Seed one customer so tests can reference its integer ID
    customer = Customer(
        garage_id=1,
        type=CustomerType.individual,
        full_name="Default Test Customer",
        status=CustomerStatus.active,
    )
    seeded_db.add(customer)
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def ae_client(
    ae_seeded_db: AsyncSession, mock_redis
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield ae_seeded_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared helpers
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


async def _get_customer_id(db: AsyncSession) -> int:
    result = await db.execute(select(Customer).limit(1))
    return result.scalar_one().id


async def _create_and_issue_invoice(
    client: AsyncClient,
    token: str,
    customer_id: int,
    unit_price_minor: int = 10000,
) -> dict:
    """Create a draft invoice with one line and issue it. Returns issued invoice dict."""
    resp = await client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "currency": "EUR",
            # issue_invoice() requires a due date to be set — see
            # app/modules/invoice/service.py's "Une date d'échéance est
            # requise pour émettre la facture." check.
            "due_at": (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat(),
            "lines": [
                {
                    "kind": "service",
                    "description": "Prestation",
                    "quantity": "1.000",
                    "unit_price_minor": unit_price_minor,
                    "discount_percent": "0.00",
                    "vat_rate": "20.00",
                }
            ],
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()

    resp = await client.post(
        f"/api/v1/invoices/{inv['public_id']}/issue",
        headers={**auth(token), "If-Match": str(inv["version"])},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _record_payment(
    client: AsyncClient, token: str, inv_id: int, amount_minor: int
) -> dict:
    resp = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount_minor": amount_minor,
            "payment_method": "cash",
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _mock_upload():
    """Context manager that mocks the S3 upload call."""
    return patch(
        "app.modules.documents.storage.upload_bytes",
        new_callable=AsyncMock,
        return_value=None,
    )


async def _run_export(client: AsyncClient, token: str, fmt: str = "generic_csv") -> dict:
    with _mock_upload():
        resp = await client.post(
            "/api/v1/accounting-exports",
            json={
                "period_start": "2020-01-01",
                "period_end": "2099-12-31",
                "format": fmt,
            },
            headers=auth(token),
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Formatter unit tests (pure Python, no DB)
# ---------------------------------------------------------------------------


class TestFormatters:
    def _sample_data(self):
        invoices = [
            {
                "id": 1,
                "doc_number": "FAC-0001",
                "issued_at": "2024-01-15",
                "customer_name": "Client Dupont",
                "amount_ht": 100000,
                "vat_amount": 20000,
                "amount_ttc": 120000,
                "is_exported": False,
            }
        ]
        payments = [
            {
                "id": 1,
                "doc_number": "FAC-0001",
                "paid_at": "2024-01-20",
                "customer_name": "Client Dupont",
                "method": "bank_transfer",
                "amount_minor": 120000,
                "is_exported": False,
            }
        ]
        supplier_invoices = [
            {
                "id": 1,
                "number": "FAF-0001",
                "received_at": "2024-01-10",
                "supplier_name": "Fournisseur X",
                "total_ht": 50000,
                "vat_amount": 10000,
                "total_ttc": 60000,
                "is_exported": False,
            }
        ]
        vat_summary = [
            {
                "vat_rate": 20.0,
                "sales_base_ht": 100000,
                "vat_collected": 20000,
                "purchases_base_ht": 50000,
                "vat_deductible": 10000,
            }
        ]
        return invoices, payments, supplier_invoices, vat_summary

    def test_generic_csv_produces_four_journal_files(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("generic_csv", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
        assert names == {
            "journal_ventes.csv",
            "journal_reglements.csv",
            "journal_achats.csv",
            "balance_tva.csv",
        }

    def test_sage_contains_pcg_accounts(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("sage", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            sales = zf.read("journal_ventes.csv").decode("utf-8-sig")
        assert "411000" in sales   # Clients
        assert "445710" in sales   # TVA collectée

    def test_sage_uses_semicolon_and_dd_mm_yyyy(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("sage", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            sales = zf.read("journal_ventes.csv").decode("utf-8-sig")
        assert ";" in sales
        assert "15/01/2024" in sales

    def test_cegid_uses_tab_and_iso_dates(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("cegid", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            sales = zf.read("journal_ventes.csv").decode("utf-8-sig")
        assert "\t" in sales
        assert "2024-01-15" in sales

    def test_ebp_produces_valid_zip(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("ebp", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert len(zf.namelist()) == 4

    def test_unknown_format_falls_back_to_generic(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("unknown_xyz", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert "journal_ventes.csv" in zf.namelist()

    def test_purchases_journal_sage_pcg_accounts(self):
        inv, pay, si, vat = self._sample_data()
        data = generate_zip("sage", inv, pay, si, vat)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            achats = zf.read("journal_achats.csv").decode("utf-8-sig")
        assert "607000" in achats   # Achats
        assert "445660" in achats   # TVA déductible
        assert "401000" in achats   # Fournisseurs

    def test_empty_data_produces_valid_zip(self):
        data = generate_zip("generic_csv", [], [], [], [])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert len(zf.namelist()) == 4


# ---------------------------------------------------------------------------
# Preview endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_empty_period_returns_zeros(ae_client: AsyncClient):
    token = await _login(ae_client)
    resp = await ae_client.get(
        "/api/v1/accounting-exports/preview",
        params={"period_start": "2024-01-01", "period_end": "2024-01-31"},
        headers=auth(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["pending_invoices"] == 0
    assert data["already_exported_invoices"] == 0
    assert data["warning"] is None


@pytest.mark.asyncio
async def test_preview_requires_auth(ae_client: AsyncClient):
    resp = await ae_client.get(
        "/api/v1/accounting-exports/preview",
        params={"period_start": "2024-01-01", "period_end": "2024-01-31"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Export creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_export_completed_status(ae_client: AsyncClient):
    token = await _login(ae_client)
    export = await _run_export(ae_client, token)
    assert export["status"] == "completed"
    assert export["format"] == "generic_csv"
    assert export["record_counts"] is not None


@pytest.mark.asyncio
async def test_create_export_marks_invoices_as_exported(
    ae_client: AsyncClient, ae_seeded_db: AsyncSession
):
    token = await _login(ae_client)
    customer_id = await _get_customer_id(ae_seeded_db)
    inv = await _create_and_issue_invoice(ae_client, token, customer_id)

    export = await _run_export(ae_client, token)
    assert export["record_counts"]["invoices"] >= 1

    # Re-fetch invoice — is_exported should be True
    resp = await ae_client.get(f"/api/v1/invoices/{inv['public_id']}", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json()["is_exported"] is True


@pytest.mark.asyncio
async def test_create_export_invalid_format_returns_400(ae_client: AsyncClient):
    token = await _login(ae_client)
    with _mock_upload():
        resp = await ae_client.post(
            "/api/v1/accounting-exports",
            json={
                "period_start": "2024-01-01",
                "period_end": "2024-01-31",
                "format": "bad_format",
            },
            headers=auth(token),
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_export_records_payment(
    ae_client: AsyncClient, ae_seeded_db: AsyncSession
):
    token = await _login(ae_client)
    customer_id = await _get_customer_id(ae_seeded_db)
    inv = await _create_and_issue_invoice(ae_client, token, customer_id, unit_price_minor=20000)
    # total = 20000 + 20% VAT = 24000
    await _record_payment(ae_client, token, inv["id"], 24000)

    export = await _run_export(ae_client, token)
    assert export["record_counts"]["payments"] >= 1


@pytest.mark.asyncio
async def test_list_exports_returns_paginated_result(ae_client: AsyncClient):
    token = await _login(ae_client)
    resp = await ae_client.get("/api/v1/accounting-exports", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data and "page" in data


@pytest.mark.asyncio
async def test_get_export_by_id(ae_client: AsyncClient):
    token = await _login(ae_client)
    export = await _run_export(ae_client, token)
    pub_id = export["public_id"]

    resp = await ae_client.get(
        f"/api/v1/accounting-exports/{pub_id}", headers=auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["public_id"] == pub_id


@pytest.mark.asyncio
async def test_get_export_not_found(ae_client: AsyncClient):
    token = await _login(ae_client)
    resp = await ae_client.get(
        "/api/v1/accounting-exports/00000000-0000-0000-0000-000000000000",
        headers=auth(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Re-export prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_export_excludes_already_exported_records(
    ae_client: AsyncClient, ae_seeded_db: AsyncSession
):
    token = await _login(ae_client)
    customer_id = await _get_customer_id(ae_seeded_db)
    await _create_and_issue_invoice(ae_client, token, customer_id)

    # First export picks up the invoice
    first = await _run_export(ae_client, token)
    first_count = first["record_counts"]["invoices"]
    assert first_count >= 1

    # Second export over same period — already-exported invoice excluded
    second = await _run_export(ae_client, token)
    assert second["record_counts"]["invoices"] < first_count


@pytest.mark.asyncio
async def test_preview_shows_warning_after_export(
    ae_client: AsyncClient, ae_seeded_db: AsyncSession
):
    token = await _login(ae_client)
    customer_id = await _get_customer_id(ae_seeded_db)
    await _create_and_issue_invoice(ae_client, token, customer_id)

    await _run_export(ae_client, token)

    resp = await ae_client.get(
        "/api/v1/accounting-exports/preview",
        params={"period_start": "2020-01-01", "period_end": "2099-12-31"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["already_exported_invoices"] >= 1
    assert data["warning"] is not None
    assert "already been exported" in data["warning"]


# ---------------------------------------------------------------------------
# Lock enforcement: exported invoice cannot be cancelled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exported_invoice_cannot_be_cancelled(
    ae_client: AsyncClient, ae_seeded_db: AsyncSession
):
    token = await _login(ae_client)
    customer_id = await _get_customer_id(ae_seeded_db)
    inv = await _create_and_issue_invoice(ae_client, token, customer_id)
    inv_public_id = inv["public_id"]

    await _run_export(ae_client, token)

    # Re-fetch to get current version after export updated the invoice
    fetch = await ae_client.get(f"/api/v1/invoices/{inv_public_id}", headers=auth(token))
    assert fetch.status_code == 200
    version = fetch.json()["version"]

    cancel_resp = await ae_client.post(
        f"/api/v1/invoices/{inv_public_id}/cancel",
        headers={**auth(token), "If-Match": str(version)},
    )
    # Service raises InvoiceStateError → router returns 409
    assert cancel_resp.status_code == 409, (
        f"Expected 409 for exported invoice cancel, got {cancel_resp.status_code}: {cancel_resp.text}"
    )
    assert "exported" in cancel_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Lock enforcement: exported payment cannot be refunded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exported_payment_cannot_be_refunded(
    ae_client: AsyncClient, ae_seeded_db: AsyncSession
):
    token = await _login(ae_client)
    customer_id = await _get_customer_id(ae_seeded_db)
    inv = await _create_and_issue_invoice(ae_client, token, customer_id, unit_price_minor=30000)
    # total = 30000 + 20% = 36000
    payment = await _record_payment(ae_client, token, inv["id"], 36000)
    payment_id = payment["id"]

    await _run_export(ae_client, token)

    # Credit notes are still allowed against exported invoices
    cn_resp = await ae_client.post(
        "/api/v1/credit-notes",
        json={
            "invoice_id": inv["id"],
            "total_minor": 5000,
            "reason": "Erreur partielle",
        },
        headers=auth(token),
    )
    assert cn_resp.status_code == 201, cn_resp.text
    cn_id = cn_resp.json()["id"]

    issue_resp = await ae_client.post(
        f"/api/v1/credit-notes/{cn_id}/issue",
        headers=auth(token),
    )
    assert issue_resp.status_code == 200, issue_resp.text

    # Attempt to refund the exported payment — must be blocked
    refund_resp = await ae_client.post(
        "/api/v1/refunds",
        json={
            "payment_id": payment_id,
            "credit_note_id": cn_id,
            "amount_minor": 5000,
            "payment_method": "cash",
        },
        headers=auth(token),
    )
    # CreditNoteStateError → 422
    assert refund_resp.status_code == 422, (
        f"Expected 422 for exported payment refund, got {refund_resp.status_code}: {refund_resp.text}"
    )
    assert "exported" in refund_resp.json()["detail"].lower()
