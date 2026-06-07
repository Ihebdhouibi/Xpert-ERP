"""PDF generation service — Jinja2 templates rendered via WeasyPrint.

All document text content (garage name, legal mentions, bank details …) is
sourced from ``Settings`` (CFG_* environment variables).
WeasyPrint is synchronous; we run it in a thread-pool executor so the async
event-loop is not blocked.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.customer import repository as customer_repo
from app.modules.delivery_note import repository as delivery_note_repo
from app.modules.invoice import repository as invoice_repo
from app.modules.quotation import repository as quotation_repo
from app.modules.vehicles import repository as vehicle_repo

logger = get_logger("pdf.service")

# ---------------------------------------------------------------------------
# Jinja2 environment
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = (
    Path(__file__).parent  # …/app/modules/pdf/
    .parent  # …/app/modules/
    .parent  # …/app/
    .parent  # …/backend/
    / "templates"
    / "documents"
)


def _make_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["money"] = _fmt_money
    return env


_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = _make_jinja_env()
    return _jinja_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_money(minor: int | None, symbol: str = "€") -> str:
    """Format a minor-unit amount (cents) as a human-readable string."""
    if minor is None:
        return f"0.00 {symbol}"
    value = minor / 100
    formatted = f"{value:,.2f}".replace(",", "\u202f")  # narrow no-break space
    return f"{formatted} {symbol}"


def _render_pdf_sync(html_string: str, base_url: str) -> bytes:
    """Blocking WeasyPrint call — must be run in a thread executor."""
    from weasyprint import HTML  # local import so test mocks work cleanly

    return HTML(string=html_string, base_url=base_url).write_pdf()


def _garage_context() -> dict[str, Any]:
    s = get_settings()
    return {
        "garage_name": s.pdf_garage_name,
        "garage_address": s.pdf_garage_address,
        "garage_phone": s.pdf_garage_phone,
        "garage_email": s.pdf_garage_email,
        "garage_logo_path": s.pdf_garage_logo_path,
        "vat_number": s.pdf_vat_number,
        "legal_mention": s.pdf_legal_mention,
        "bank_details": s.pdf_bank_details,
        "footer_text": s.pdf_footer_text,
        "currency_symbol": s.pdf_currency_symbol,
        "payment_terms": s.pdf_payment_terms,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def render_quotation_pdf(
    db: AsyncSession, *, quotation_id: int, garage_id: int
) -> bytes:
    """Fetch the quotation from DB, render HTML template, return PDF bytes."""
    logger.info("render_quotation_pdf_start", quotation_id=quotation_id, garage_id=garage_id)
    try:
        quotation = await quotation_repo.get_by_id(db, quotation_id, garage_id)
        if quotation is None:
            raise ValueError(f"Quotation {quotation_id} not found")

        customer = await customer_repo.get_by_id(db, garage_id, quotation.customer_id)
        vehicle = None
        if quotation.vehicle_id:
            vehicle = await vehicle_repo.get_by_id(
                db, vehicle_id=quotation.vehicle_id, garage_id=garage_id
            )

        settings = get_settings()
        ctx: dict[str, Any] = {
            **_garage_context(),
            "doc": quotation,
            "customer": customer,
            "vehicle": vehicle,
            "currency_symbol": settings.pdf_currency_symbol,
        }

        env = _get_jinja_env()
        html_string = env.get_template("quotation.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(
            None, _render_pdf_sync, html_string, base_url
        )
        logger.info("render_quotation_pdf_success", quotation_id=quotation_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_quotation_pdf_error", quotation_id=quotation_id, garage_id=garage_id)
        raise


async def render_delivery_note_pdf(
    db: AsyncSession, *, delivery_note_id: int, garage_id: int
) -> bytes:
    """Fetch the delivery note from DB, render HTML template, return PDF bytes."""
    logger.info("render_delivery_note_pdf_start", delivery_note_id=delivery_note_id, garage_id=garage_id)
    try:
        dn = await delivery_note_repo.get_by_id(db, delivery_note_id, garage_id)
        if dn is None:
            raise ValueError(f"Delivery note {delivery_note_id} not found")

        customer = await customer_repo.get_by_id(db, garage_id, dn.customer_id)
        vehicle = None
        if dn.vehicle_id:
            vehicle = await vehicle_repo.get_by_id(
                db, vehicle_id=dn.vehicle_id, garage_id=garage_id
            )

        settings = get_settings()
        ctx: dict[str, Any] = {
            **_garage_context(),
            "doc": dn,
            "customer": customer,
            "vehicle": vehicle,
            "currency_symbol": settings.pdf_currency_symbol,
        }

        env = _get_jinja_env()
        html_string = env.get_template("delivery_note.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(
            None, _render_pdf_sync, html_string, base_url
        )
        logger.info("render_delivery_note_pdf_success", delivery_note_id=delivery_note_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_delivery_note_pdf_error", delivery_note_id=delivery_note_id, garage_id=garage_id)
        raise


async def render_invoice_pdf(
    db: AsyncSession, *, invoice_id: int, garage_id: int
) -> bytes:
    """Fetch the invoice from DB, render HTML template, return PDF bytes."""
    logger.info("render_invoice_pdf_start", invoice_id=invoice_id, garage_id=garage_id)
    try:
        invoice = await invoice_repo.get_by_id(db, invoice_id, garage_id)
        if invoice is None:
            raise ValueError(f"Invoice {invoice_id} not found")

        customer = await customer_repo.get_by_id(db, garage_id, invoice.customer_id)
        vehicle = None
        if invoice.vehicle_id:
            vehicle = await vehicle_repo.get_by_id(
                db, vehicle_id=invoice.vehicle_id, garage_id=garage_id
            )

        settings = get_settings()
        ctx: dict[str, Any] = {
            **_garage_context(),
            "doc": invoice,
            "customer": customer,
            "vehicle": vehicle,
            "currency_symbol": settings.pdf_currency_symbol,
        }

        env = _get_jinja_env()
        html_string = env.get_template("invoice.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(
            None, _render_pdf_sync, html_string, base_url
        )
        logger.info("render_invoice_pdf_success", invoice_id=invoice_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_invoice_pdf_error", invoice_id=invoice_id, garage_id=garage_id)
        raise
