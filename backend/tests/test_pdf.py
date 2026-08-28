"""Tests for the PDF module (#30) — template rendering and service layer."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/xpert_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY_ID", "testkey")
os.environ.setdefault("S3_SECRET_ACCESS_KEY", "testsecret")
os.environ.setdefault("S3_BUCKET_DOCUMENTS", "test-documents")
os.environ.setdefault("S3_BUCKET_MEDIA", "test-media")

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password
from app.modules.pdf.service import (
    _BACKEND_DIR,
    _fmt_money,
    _get_jinja_env,
    _make_jinja_env,
    _nature_of_operation,
    _resolve_logo_url,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

PERMISSIONS = ["quotation.read", "invoice.read"]


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_pdf_db(db_session: AsyncSession) -> AsyncSession:
    """Seed: pdf permissions, admin role, user."""
    perms = [
        Permission(
            code=code,
            resource=code.split(".")[0],
            action=code.split(".")[-1],
            description="",
        )
        for code in PERMISSIONS
    ]
    role = Role(code="admin", display_name="Admin", is_system=True)
    db_session.add_all([*perms, role])
    await db_session.flush()

    for perm in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = AppUser(
        garage_id=1,
        email="admin@test.com",
        full_name="Test Admin",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    return db_session


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
async def pdf_client(
    seeded_pdf_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_pdf_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers for building mock document objects
# ---------------------------------------------------------------------------

def _make_line(
    *,
    kind_value: str = "labor",
    description: str = "Main-d'œuvre",
    quantity: float = 1.0,
    unit_price_minor: int = 10000,
    discount_percent: float | None = None,
    vat_rate: float = 20.0,
    line_total_minor: int = 10000,
) -> SimpleNamespace:
    kind = SimpleNamespace(value=kind_value)
    return SimpleNamespace(
        kind=kind,
        description=description,
        quantity=Decimal(str(quantity)),
        unit_price_minor=unit_price_minor,
        discount_percent=Decimal(str(discount_percent)) if discount_percent else None,
        vat_rate=Decimal(str(vat_rate)),
        line_total_minor=line_total_minor,
    )


def _make_quotation(*, with_vehicle: bool = False, with_discount: bool = False) -> SimpleNamespace:
    status = SimpleNamespace(value="draft")
    lines = [
        _make_line(
            description="Révision complète",
            quantity=1.0,
            unit_price_minor=15000,
            vat_rate=20.0,
            line_total_minor=15000,
        ),
        _make_line(
            kind_value="part",
            description="Filtre à huile",
            quantity=2.0,
            unit_price_minor=500,
            vat_rate=20.0,
            line_total_minor=1000,
        ),
    ]
    return SimpleNamespace(
        doc_number="QUOT-2026-00001",
        status=status,
        created_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        valid_until=datetime(2026, 2, 14, tzinfo=timezone.utc),
        lines=lines,
        subtotal_minor=16000,
        discount_minor=500 if with_discount else 0,
        vat_minor=3100,
        total_minor=18600,
        vehicle_id=1 if with_vehicle else None,
        notes="Vérifier les plaquettes de frein.",
        customer_id=1,
    )


def _make_invoice(*, with_payment: bool = False) -> SimpleNamespace:
    status_val = "partial" if with_payment else "issued"
    status = SimpleNamespace(value=status_val)
    lines = [
        _make_line(
            description="Remplacement plaquettes de frein",
            quantity=1.0,
            unit_price_minor=8000,
            vat_rate=20.0,
            line_total_minor=8000,
        ),
    ]
    return SimpleNamespace(
        doc_number="INV-2026-00001",
        status=status,
        issued_at=datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc),
        due_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
        lines=lines,
        subtotal_minor=8000,
        discount_minor=0,
        vat_minor=1600,
        total_minor=9600,
        paid_amount_minor=5000 if with_payment else 0,
        outstanding_minor=4600 if with_payment else 9600,
        vehicle_id=None,
        quotation_id=None,
        notes=None,
        customer_id=1,
    )


def _make_customer() -> SimpleNamespace:
    return SimpleNamespace(
        full_name="Jean Dupont",
        company_name="Garage Central",
        address={"street": "12 Rue de la Paix", "city": "Paris", "postal_code": "75001"},
        phone_e164="+33612345678",
        email="jean.dupont@example.com",
        fiscal_id="FR12345678901",
    )


def _make_vehicle() -> SimpleNamespace:
    return SimpleNamespace(
        make="Renault",
        model="Clio",
        trim="1.5 dCi 90ch",
        registration="AB-123-CD",
        vin="VF1BB1C0H12345678",
        year=2019,
        mileage_current=75000,
    )


def _base_ctx(*, currency_symbol: str = "€") -> dict:
    return {
        "garage_name": "Test Garage",
        "garage_address": "1 Rue Test, 75001 Paris",
        "garage_phone": "+33 1 23 45 67 89",
        "garage_email": "contact@testgarage.fr",
        "garage_logo_path": "",
        "vat_number": "FR99123456789",
        "legal_mention": "Mention légale de test.",
        "bank_iban": "FR76 0000 0000 0000 0000 0000 000",
        "bank_bic": "TESTFRPP",
        "bank_holder": "TEST GARAGE SARL",
        "footer_text": "Merci de votre confiance.",
        "payment_terms": "Paiement à 30 jours",
        "currency_symbol": currency_symbol,
    }


# ---------------------------------------------------------------------------
# Unit tests: _fmt_money
# ---------------------------------------------------------------------------


class TestResolveLogoUrl:
    """A bare filesystem path is not a URL: on Windows ``D:\\x\\logo.png``
    parses as scheme ``d:`` and the image silently fails to load, leaving the
    document with only alt text where the logo should be."""

    def test_absolute_path_becomes_file_uri(self) -> None:
        logo = _BACKEND_DIR / "assets" / "logo-pdf.png"
        result = _resolve_logo_url(str(logo))
        assert result.startswith("file://")
        assert result.endswith("logo-pdf.png")

    def test_path_relative_to_backend_root_is_resolved(self) -> None:
        result = _resolve_logo_url("assets/logo-pdf.png")
        assert result.startswith("file://")
        assert result.endswith("logo-pdf.png")

    def test_empty_stays_empty(self) -> None:
        assert _resolve_logo_url("") == ""
        assert _resolve_logo_url(None) == ""

    def test_qualified_urls_pass_through(self) -> None:
        for url in ("https://cdn.example/logo.png", "file:///tmp/logo.png", "data:image/png;base64,AA=="):
            assert _resolve_logo_url(url) == url

    def test_unresolvable_path_passes_through(self) -> None:
        assert _resolve_logo_url("assets/does-not-exist.png") == "assets/does-not-exist.png"


class TestFmtMoney:
    def test_basic_cents(self) -> None:
        result = _fmt_money(1050)
        assert "10" in result
        assert "50" in result
        assert "€" in result

    def test_zero(self) -> None:
        result = _fmt_money(0)
        assert "0,00" in result

    def test_none_returns_zero(self) -> None:
        result = _fmt_money(None)  # type: ignore[arg-type]
        assert "0,00" in result
        assert "€" in result

    def test_custom_symbol(self) -> None:
        result = _fmt_money(500, "TND")
        assert "TND" in result
        assert "5,00" in result

    def test_french_decimal_and_thousands_separators(self) -> None:
        """Comma decimal separator, narrow no-break space for thousands."""
        result = _fmt_money(1_234_567)
        assert result.replace(chr(0x202F), " ") == "12 345,67 \u20ac"
        assert "." not in result

    def test_large_amount(self) -> None:
        result = _fmt_money(1_000_000)  # 10 000.00
        assert "€" in result


class TestNatureOfOperation:
    def _line(self, kind: str) -> SimpleNamespace:
        return SimpleNamespace(kind=SimpleNamespace(value=kind))

    def test_all_labor_is_services(self) -> None:
        assert _nature_of_operation([self._line("labor")]) == "Prestation de services"

    def test_all_service_kind_is_services(self) -> None:
        assert _nature_of_operation([self._line("service")]) == "Prestation de services"

    def test_all_part_is_goods(self) -> None:
        assert _nature_of_operation([self._line("part")]) == "Vente de biens"

    def test_mixed_is_both(self) -> None:
        result = _nature_of_operation([self._line("labor"), self._line("part")])
        assert result == "Vente de biens et prestation de services"

    def test_other_kind_defaults_to_services(self) -> None:
        assert _nature_of_operation([self._line("other")]) == "Prestation de services"

    def test_no_lines_defaults_to_services(self) -> None:
        assert _nature_of_operation([]) == "Prestation de services"


# ---------------------------------------------------------------------------
# Unit tests: Jinja2 template rendering (no WeasyPrint)
# ---------------------------------------------------------------------------


class TestQuotationTemplate:
    def test_renders_without_error(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(),
            doc=_make_quotation(),
            customer=_make_customer(),
            vehicle=None,
        )
        assert "<!DOCTYPE html>" in html
        assert "Devis" in html

    def test_contains_doc_number(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        quotation = _make_quotation()
        html = tmpl.render(**_base_ctx(), doc=quotation, customer=_make_customer(), vehicle=None)
        assert "QUOT-2026-00001" in html

    def test_contains_customer_info(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_quotation(), customer=_make_customer(), vehicle=None
        )
        # Company customers are addressed by their company name — the legal
        # addressee — rather than by the contact person's name.
        assert "Garage Central" in html
        assert "75001" in html

    def test_contains_line_items(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_quotation(), customer=_make_customer(), vehicle=None
        )
        assert "Révision complète" in html
        assert "Filtre à huile" in html

    def test_contains_totals(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_quotation(), customer=_make_customer(), vehicle=None
        )
        assert "Total estimé TTC" in html
        assert "Total estimé HT" in html

    def test_renders_with_vehicle(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(),
            doc=_make_quotation(with_vehicle=True),
            customer=_make_customer(),
            vehicle=_make_vehicle(),
        )
        assert "Renault" in html
        assert "Clio" in html
        assert "AB-123-CD" in html
        assert "75000" in html
        assert "1.5 dCi 90ch" in html

    def test_renders_with_discount(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(),
            doc=_make_quotation(with_discount=True),
            customer=_make_customer(),
            vehicle=None,
        )
        assert "Remise" in html

    def test_renders_garage_info(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_quotation(), customer=_make_customer(), vehicle=None
        )
        assert "Test Garage" in html
        assert "FR99123456789" in html

    def test_renders_payment_terms(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_quotation(), customer=_make_customer(), vehicle=None
        )
        assert "Paiement à 30 jours" in html

    def test_renders_legal_mention(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_quotation(), customer=_make_customer(), vehicle=None
        )
        assert "Mention légale de test." in html

    def test_renders_without_customer(self) -> None:
        """Customer can be None (e.g. deleted customer) — must not crash."""
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        html = tmpl.render(**_base_ctx(), doc=_make_quotation(), customer=None, vehicle=None)
        assert "<!DOCTYPE html>" in html

    def test_renders_with_empty_lines(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("quotation.html")
        doc = _make_quotation()
        doc.lines = []
        html = tmpl.render(**_base_ctx(), doc=doc, customer=_make_customer(), vehicle=None)
        assert "Aucune ligne" in html


class TestInvoiceTemplate:
    def test_renders_without_error(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_invoice(), customer=_make_customer(), vehicle=None
        )
        assert "<!DOCTYPE html>" in html
        assert "Facture" in html

    def test_contains_doc_number(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_invoice(), customer=_make_customer(), vehicle=None
        )
        assert "INV-2026-00001" in html

    def test_shows_paid_status_colour(self) -> None:
        """Invoices only get a distinct title treatment for "cancelled" —
        "paid" must still render the plain title without crashing or
        picking up the cancelled wording."""
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        doc = _make_invoice()
        doc.status = SimpleNamespace(value="paid")
        html = tmpl.render(**_base_ctx(), doc=doc, customer=_make_customer(), vehicle=None)
        assert "Facture" in html
        assert "Annulée" not in html

    def test_shows_cancelled_status_colour(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        doc = _make_invoice()
        doc.status = SimpleNamespace(value="cancelled")
        html = tmpl.render(**_base_ctx(), doc=doc, customer=_make_customer(), vehicle=None)
        assert "Annulée" in html

    def test_shows_partial_payment(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        html = tmpl.render(
            **_base_ctx(),
            doc=_make_invoice(with_payment=True),
            customer=_make_customer(),
            vehicle=None,
        )
        assert "Montant réglé" in html
        assert "Net à payer" in html

    def test_renders_bank_details(self) -> None:
        """Bank details render once, in the shared running footer — not
        inline in the invoice body — so every document type gets them."""
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        html = tmpl.render(
            **_base_ctx(), doc=_make_invoice(), customer=_make_customer(), vehicle=None
        )
        assert "FR76 0000 0000 0000 0000 0000 000" in html
        assert "TESTFRPP" in html
        assert "TEST GARAGE SARL" in html

    def test_renders_without_customer(self) -> None:
        env = _make_jinja_env()
        tmpl = env.get_template("invoice.html")
        html = tmpl.render(**_base_ctx(), doc=_make_invoice(), customer=None, vehicle=None)
        assert "<!DOCTYPE html>" in html


# ---------------------------------------------------------------------------
# Service tests (mock WeasyPrint + repositories)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPdfServiceQuotation:
    async def test_render_quotation_pdf_returns_bytes(
        self, db_session: AsyncSession, mock_redis: AsyncMock
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        mock_quotation = _make_quotation()
        mock_customer = _make_customer()
        fake_pdf_bytes = b"%PDF-1.4 fake pdf"

        with (
            patch.object(pdf_svc, "_render_pdf_sync", return_value=fake_pdf_bytes),
            patch(
                "app.modules.quotation.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_quotation,
            ),
            patch(
                "app.modules.customer.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_customer,
            ),
            patch(
                "app.modules.vehicles.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await pdf_svc.render_quotation_pdf(
                db_session, quotation_id=1, garage_id=1, redis=mock_redis
            )
            assert isinstance(result, bytes)
            assert result == fake_pdf_bytes

    async def test_render_quotation_pdf_raises_on_not_found(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        with patch(
            "app.modules.quotation.repository.get_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(ValueError, match="not found"):
                await pdf_svc.render_quotation_pdf(
                    db_session, quotation_id=999, garage_id=1, redis=AsyncMock()
                )


@pytest.mark.asyncio
class TestPdfServiceInvoice:
    async def test_render_invoice_pdf_returns_bytes(
        self, db_session: AsyncSession, mock_redis: AsyncMock
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        mock_invoice = _make_invoice()
        mock_customer = _make_customer()
        fake_pdf_bytes = b"%PDF-1.4 fake invoice pdf"

        with (
            patch.object(pdf_svc, "_render_pdf_sync", return_value=fake_pdf_bytes),
            patch(
                "app.modules.invoice.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_invoice,
            ),
            patch(
                "app.modules.customer.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_customer,
            ),
            patch(
                "app.modules.vehicles.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await pdf_svc.render_invoice_pdf(
                db_session, invoice_id=1, garage_id=1, redis=mock_redis
            )
            assert isinstance(result, bytes)
            assert result == fake_pdf_bytes

    async def test_render_invoice_pdf_raises_on_not_found(
        self, db_session: AsyncSession
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        with patch(
            "app.modules.invoice.repository.get_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(ValueError, match="not found"):
                await pdf_svc.render_invoice_pdf(
                    db_session, invoice_id=999, garage_id=1, redis=AsyncMock()
                )

    async def test_render_invoice_pdf_fetches_vehicle_when_present(
        self, db_session: AsyncSession, mock_redis: AsyncMock
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        mock_invoice = _make_invoice()
        mock_invoice.vehicle_id = 42
        mock_customer = _make_customer()
        mock_vehicle = _make_vehicle()
        fake_pdf_bytes = b"%PDF-1.4 fake"

        with (
            patch.object(pdf_svc, "_render_pdf_sync", return_value=fake_pdf_bytes),
            patch(
                "app.modules.invoice.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_invoice,
            ),
            patch(
                "app.modules.customer.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_customer,
            ),
            patch(
                "app.modules.vehicles.repository.get_by_id",
                new_callable=AsyncMock,
                return_value=mock_vehicle,
            ) as mock_veh_repo,
        ):
            result = await pdf_svc.render_invoice_pdf(
                db_session, invoice_id=1, garage_id=1, redis=mock_redis
            )
            mock_veh_repo.assert_called_once()
            assert result == fake_pdf_bytes


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPdfEndpoints:
    async def _login(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    async def test_quotation_pdf_unauthenticated_returns_401(
        self, pdf_client: AsyncClient
    ) -> None:
        resp = await pdf_client.get("/api/v1/pdf/quotations/1")
        assert resp.status_code == 401

    async def test_invoice_pdf_unauthenticated_returns_401(
        self, pdf_client: AsyncClient
    ) -> None:
        resp = await pdf_client.get("/api/v1/pdf/invoices/1")
        assert resp.status_code == 401

    async def test_quotation_pdf_not_found_returns_404(
        self, pdf_client: AsyncClient
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        token = await self._login(pdf_client)
        with patch.object(
            pdf_svc,
            "render_quotation_pdf",
            new_callable=AsyncMock,
            side_effect=ValueError("Quotation 999 not found"),
        ):
            resp = await pdf_client.get(
                "/api/v1/pdf/quotations/999",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404

    async def test_invoice_pdf_not_found_returns_404(
        self, pdf_client: AsyncClient
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        token = await self._login(pdf_client)
        with patch.object(
            pdf_svc,
            "render_invoice_pdf",
            new_callable=AsyncMock,
            side_effect=ValueError("Invoice 999 not found"),
        ):
            resp = await pdf_client.get(
                "/api/v1/pdf/invoices/999",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404

    async def test_quotation_pdf_returns_pdf_content_type(
        self, pdf_client: AsyncClient
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        token = await self._login(pdf_client)
        with patch.object(
            pdf_svc,
            "render_quotation_pdf",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake",
        ):
            resp = await pdf_client.get(
                "/api/v1/pdf/quotations/1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content == b"%PDF-1.4 fake"

    async def test_invoice_pdf_returns_pdf_content_type(
        self, pdf_client: AsyncClient
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        token = await self._login(pdf_client)
        with patch.object(
            pdf_svc,
            "render_invoice_pdf",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake invoice",
        ):
            resp = await pdf_client.get(
                "/api/v1/pdf/invoices/1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content == b"%PDF-1.4 fake invoice"

    async def test_quotation_pdf_content_disposition_header(
        self, pdf_client: AsyncClient
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        token = await self._login(pdf_client)
        with patch.object(
            pdf_svc,
            "render_quotation_pdf",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake",
        ):
            resp = await pdf_client.get(
                "/api/v1/pdf/quotations/7",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "devis-7.pdf" in cd

    async def test_invoice_pdf_content_disposition_header(
        self, pdf_client: AsyncClient
    ) -> None:
        from app.modules.pdf import service as pdf_svc

        token = await self._login(pdf_client)
        with patch.object(
            pdf_svc,
            "render_invoice_pdf",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake",
        ):
            resp = await pdf_client.get(
                "/api/v1/pdf/invoices/3",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "facture-3.pdf" in cd
