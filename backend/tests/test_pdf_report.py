"""Tests for PDF report generation (Issue #23)."""
from __future__ import annotations

import types
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import Permission, Role, RolePermission
from app.modules.repair_order.models import RepairOrder, ROStatus

RO_PERMISSIONS = (
    "repair_order.read",
    "repair_order.create",
    "repair_order.update",
    "repair_order.delete",
    "repair_order.transition",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def pdf_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
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
async def pdf_client(
    pdf_seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield pdf_seeded_db

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


async def _create_ro(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/repair-orders",
        json={"customer_id": 1, "description": "Vidange + filtre à huile"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Unit tests: HTML template rendering
# ---------------------------------------------------------------------------

class _FakeROLine:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeRO:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.customer_id = 1
        self.vehicle_id = None
        self.description = "Remplacement plaquettes de frein"
        self.status = ROStatus.in_repair
        self.priority = "high"
        self.estimated_cost_minor = 15000
        self.estimated_cost_currency = "DT"
        self.actual_cost_minor = 14500
        self.assigned_user_id = None
        self.notes = None
        self.created_at = datetime(2026, 5, 24, 10, 0, 0, tzinfo=timezone.utc)
        self.updated_at = datetime(2026, 5, 24, 12, 0, 0, tzinfo=timezone.utc)
        self.labor_lines = [
            _FakeROLine(labor_type="Main d'œuvre", duration_minutes=90, rate_minor=5000, amount_minor=7500)
        ]
        self.part_lines = [
            _FakeROLine(part_name="Plaquettes avant", quantity=1, unit_cost_minor=7000, amount_minor=7000)
        ]
        self.status_events = []


@pytest.mark.asyncio
class TestTemplateRendering:
    def _make_settings(self, **overrides):
        cfg = MagicMock()
        cfg.cfg_garage_name = overrides.get("cfg_garage_name", "Test Garage")
        cfg.cfg_garage_address = overrides.get("cfg_garage_address", "1 Rue Test, 1000 Tunis")
        cfg.cfg_garage_phone = overrides.get("cfg_garage_phone", "+216 71 000 000")
        cfg.cfg_garage_email = overrides.get("cfg_garage_email", "test@garage.tn")
        cfg.cfg_logo_url = overrides.get("cfg_logo_url", "")
        cfg.cfg_legal_footer = overrides.get("cfg_legal_footer", "SARL — RC 12345")
        cfg.cfg_gtk3_dll_dir = ""
        return cfg

    async def test_html_contains_garage_name(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings(cfg_garage_name="Garage Dupont")
        html = _render_html(ro, None, None, "—", settings)
        assert "Garage Dupont" in html

    async def test_html_contains_legal_footer(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings(cfg_legal_footer="RC 99999 — TVA FR12345678901")
        html = _render_html(ro, None, None, "—", settings)
        assert "RC 99999" in html

    async def test_html_contains_description(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings()
        html = _render_html(ro, None, None, "—", settings)
        assert "Remplacement plaquettes de frein" in html

    async def test_html_contains_labor_line(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings()
        html = _render_html(ro, None, None, "—", settings)
        assert "Main d'œuvre" in html

    async def test_html_contains_part_line(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings()
        html = _render_html(ro, None, None, "—", settings)
        assert "Plaquettes avant" in html

    async def test_html_uses_logo_url_when_set(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings(cfg_logo_url="https://example.com/logo.png")
        html = _render_html(ro, None, None, "—", settings)
        assert "https://example.com/logo.png" in html
        assert '<img' in html

    async def test_html_falls_back_to_text_name_when_no_logo(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings(cfg_logo_url="", cfg_garage_name="No Logo Garage")
        html = _render_html(ro, None, None, "—", settings)
        assert "No Logo Garage" in html
        assert '<img' not in html

    async def test_html_contains_mechanic_name(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        settings = self._make_settings()
        html = _render_html(ro, None, None, "Ahmed Ben Ali", settings)
        assert "Ahmed Ben Ali" in html

    async def test_status_label_in_french(self):
        from app.modules.repair_order.pdf_service import _render_html
        ro = _FakeRO()
        ro.status = ROStatus.in_repair
        settings = self._make_settings()
        html = _render_html(ro, None, None, "—", settings)
        assert "En réparation" in html


# ---------------------------------------------------------------------------
# Integration tests: endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPdfEndpoint:
    async def test_pdf_endpoint_returns_url(self, pdf_client: AsyncClient):
        token = await _login(pdf_client)
        public_id = await _create_ro(pdf_client, token)

        fake_pdf = b"%PDF-1.4 fake content"
        fake_url = "https://s3.example.com/signed-url?X-Amz-Signature=abc"

        with (
            patch(
                "app.modules.repair_order.pdf_service.generate_pdf",
                new=AsyncMock(return_value=fake_pdf),
            ),
            patch(
                "app.modules.repair_order.pdf_service.upload_pdf_and_sign",
                new=AsyncMock(return_value=fake_url),
            ),
        ):
            resp = await pdf_client.get(
                f"/api/v1/repair-orders/{public_id}/pdf",
                headers=_auth(token),
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "url" in body
        assert body["url"] == fake_url
        assert "expires_in" in body

    async def test_pdf_endpoint_requires_auth(self, pdf_client: AsyncClient):
        token = await _login(pdf_client)
        public_id = await _create_ro(pdf_client, token)
        resp = await pdf_client.get(f"/api/v1/repair-orders/{public_id}/pdf")
        assert resp.status_code == 401

    async def test_pdf_endpoint_404_for_unknown_id(self, pdf_client: AsyncClient):
        token = await _login(pdf_client)
        fake_id = str(uuid.uuid4())
        resp = await pdf_client.get(
            f"/api/v1/repair-orders/{fake_id}/pdf",
            headers=_auth(token),
        )
        assert resp.status_code == 404
