"""PDF generation service — Jinja2 templates rendered via WeasyPrint.

All document text content (garage name, legal mentions, bank details …) is
sourced from ``Settings`` (CFG_* environment variables).
WeasyPrint is synchronous; we run it in a thread-pool executor so the async
event-loop is not blocked.
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from redis.asyncio import Redis

from app.core.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.config.service import SettingsService
from app.modules.credit_note import repository as credit_note_repo
from app.modules.customer import repository as customer_repo
from app.modules.delivery_note import repository as delivery_note_repo
from app.modules.invoice import repository as invoice_repo
from app.modules.quotation import repository as quotation_repo
from app.modules.vehicles import repository as vehicle_repo
from app.modules.purchase_order.repository import PurchaseOrderRepository

logger = get_logger("pdf.service")

# ---------------------------------------------------------------------------
# Jinja2 environment
# ---------------------------------------------------------------------------

_BACKEND_DIR = (
    Path(__file__).parent  # …/app/modules/pdf/
    .parent  # …/app/modules/
    .parent  # …/app/
    .parent  # …/backend/
)

_TEMPLATES_DIR = _BACKEND_DIR / "templates" / "documents"


def _make_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["money"] = _fmt_money
    env.filters["qty"] = _fmt_qty
    env.filters["pct"] = _fmt_pct
    env.filters["date_fr"] = _fmt_date_fr
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


_FR_MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _fr_number(value: float, decimals: int = 2) -> str:
    """Render a number the French way: comma decimal, narrow-space thousands.

    ``1234.5`` → ``1 234,50``.  Python's ``,`` grouping produces the
    Anglo-Saxon form first, so the two separators are swapped through a NUL
    placeholder — replacing them in sequence would clobber one with the other.
    """
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", " ")


def _fmt_money(minor: int | None, symbol: str = "€") -> str:
    """Format a minor-unit amount (cents) as French currency: ``175,00 €``."""
    if minor is None:
        minor = 0
    value = minor / 100
    return f"{_fr_number(value)} {symbol}"


def _fmt_qty(quantity: Any, decimals: int = 2) -> str:
    """Quantities / labour hours, French-formatted: ``1,00``."""
    return _fr_number(float(quantity or 0), decimals)


def _fmt_pct(rate: Any, decimals: int = 2) -> str:
    """Percentages, French-formatted with the sign attached: ``20,00%``."""
    if rate is None:
        return ""
    return f"{_fr_number(float(rate), decimals)}%"


def _fmt_date_fr(value: Any) -> str:
    """Long-form French date: ``1 juin 2026``. Empty string when unset.

    Assembled from the date parts rather than ``strftime``: the no-pad day
    directive differs across platforms (``%-d`` vs ``%#d``), and the month
    names would follow the server locale instead of always being French.
    """
    if value is None:
        return ""
    return f"{value.day} {_FR_MONTHS[value.month - 1]} {value.year}"


_GOODS_KINDS = {"part"}
_SERVICE_KINDS = {"labor", "service"}


def _nature_of_operation(lines: Any) -> str:
    """Classify invoice/credit-note lines as goods, services, or both — the
    French tax-invoice "nature de l'opération" disclosure. Lines with no
    goods/service signal (e.g. kind="other", or no lines at all) default to
    services, since that's the common case for a garage."""
    has_goods = False
    has_services = False
    for line in lines:
        kind = getattr(line.kind, "value", line.kind)
        if kind in _GOODS_KINDS:
            has_goods = True
        elif kind in _SERVICE_KINDS:
            has_services = True

    if has_goods and has_services:
        return "Vente de biens et prestation de services"
    if has_goods:
        return "Vente de biens"
    return "Prestation de services"


def _render_pdf_sync(html_string: str, base_url: str) -> bytes:
    """Blocking WeasyPrint call — must be run in a thread executor."""
    gtk3_dll_dir = get_settings().cfg_gtk3_dll_dir
    if gtk3_dll_dir and os.name == "nt":
        os.add_dll_directory(gtk3_dll_dir)
    from weasyprint import HTML  # local import so test mocks work cleanly, and after DLL dir is registered

    return HTML(string=html_string, base_url=base_url).write_pdf()


def _resolve_logo_url(raw: str | None) -> str:
    """Turn a configured logo location into something WeasyPrint can fetch.

    A bare filesystem path is not a URL. On Windows ``D:\\assets\\logo.png``
    parses as scheme ``d:``, so the image silently fails to load and the
    document renders with only the alt text. Any value that resolves to an
    existing file — absolute, or relative to the templates directory — is
    converted to a proper ``file://`` URI. Already-qualified URLs and values
    that resolve to nothing are passed through untouched.
    """
    if not raw:
        return ""
    if re.match(r"^(?:https?|file|data):", raw, re.IGNORECASE):
        return raw

    candidates = [Path(raw)]
    if not candidates[0].is_absolute():
        # Relative values are resolved against the templates directory first
        # (next to the markup that references them), then the backend root,
        # which is where shared assets like the logo live.
        candidates = [_TEMPLATES_DIR / raw, _BACKEND_DIR / raw]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve().as_uri()
        except OSError:  # malformed path for this platform
            continue
    return raw


async def _garage_context(db: AsyncSession, redis: Redis, garage_id: int) -> dict[str, Any]:
    """Branding/legal/bank context shared by every document template.

    Reads through SettingsService (DB row for this garage → DB row for the
    global garage_id=0 default → the .env-sourced Settings value) so the
    admin Settings page can actually change what PDFs render, instead of
    only the static .env file.
    """
    env = get_settings()
    svc = SettingsService(db, redis)
    fields = {
        "garage_name": ("pdf_garage_name", env.pdf_garage_name),
        "garage_address": ("pdf_garage_address", env.pdf_garage_address),
        "garage_phone": ("pdf_garage_phone", env.pdf_garage_phone),
        "garage_email": ("pdf_garage_email", env.pdf_garage_email),
        "garage_logo_path": ("pdf_garage_logo_path", env.pdf_garage_logo_path),
        "garage_siret": ("pdf_garage_siret", env.pdf_garage_siret),
        "vat_number": ("pdf_vat_number", env.pdf_vat_number),
        "legal_mention": ("pdf_legal_mention", env.pdf_legal_mention),
        "bank_iban": ("pdf_bank_iban", env.pdf_bank_iban),
        "bank_bic": ("pdf_bank_bic", env.pdf_bank_bic),
        "bank_holder": ("pdf_bank_holder", env.pdf_bank_holder),
        "footer_text": ("pdf_footer_text", env.pdf_footer_text),
        "currency_symbol": ("pdf_currency_symbol", env.pdf_currency_symbol),
        "payment_terms": ("pdf_payment_terms", env.pdf_payment_terms),
    }
    ctx = {
        ctx_key: await svc.get_setting(cfg_key, garage_id, default=default)
        for ctx_key, (cfg_key, default) in fields.items()
    }
    ctx["garage_logo_path"] = _resolve_logo_url(ctx["garage_logo_path"])
    return ctx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def render_quotation_pdf(
    db: AsyncSession, *, quotation_id: int, garage_id: int, redis: Redis
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

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": quotation,
            "customer": customer,
            "vehicle": vehicle,
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
    db: AsyncSession, *, delivery_note_id: int, garage_id: int, redis: Redis
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

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": dn,
            "customer": customer,
            "vehicle": vehicle,
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


async def render_purchase_order_pdf(
    db: AsyncSession, *, public_id: str, garage_id: int, redis: Redis
) -> bytes:
    """Fetch the purchase order from DB, resolve names, render HTML template, return PDF bytes."""
    from sqlalchemy import select
    from app.modules.supplier.models import Supplier
    from app.modules.parts.models import Part

    logger.info("render_purchase_order_pdf_start", public_id=public_id, garage_id=garage_id)
    try:
        po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, public_id)
        if po is None:
            raise ValueError(f"Purchase order {public_id} not found")

        supplier_res = await db.execute(select(Supplier).where(Supplier.id == po.supplier_id))
        supplier = supplier_res.scalar_one_or_none()

        part_ids = list({line.part_id for line in po.lines})
        parts_map: dict[int, str] = {}
        if part_ids:
            parts_res = await db.execute(select(Part).where(Part.id.in_(part_ids)))
            parts_map = {p.id: p.name for p in parts_res.scalars()}

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": po,
            "supplier": supplier,
            "parts_map": parts_map,
        }

        env = _get_jinja_env()
        html_string = env.get_template("purchase_order.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(None, _render_pdf_sync, html_string, base_url)
        logger.info("render_purchase_order_pdf_success", public_id=public_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_purchase_order_pdf_error", public_id=public_id, garage_id=garage_id)
        raise


async def render_supplier_invoice_pdf(
    db: AsyncSession, *, public_id: str, garage_id: int, redis: Redis
) -> bytes:
    """Fetch supplier invoice, resolve supplier name, render PDF."""
    from sqlalchemy import select
    from app.modules.supplier_invoice.repository import SupplierInvoiceRepository
    from app.modules.supplier.models import Supplier

    logger.info("render_supplier_invoice_pdf_start", public_id=public_id, garage_id=garage_id)
    try:
        si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
        if si is None:
            raise ValueError(f"Supplier invoice {public_id} not found")

        supplier_res = await db.execute(select(Supplier).where(Supplier.id == si.supplier_id))
        supplier = supplier_res.scalar_one_or_none()

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": si,
            "supplier": supplier,
            "nature_of_operation": (
                "Prestation de services" if si.invoice_type == "services" else "Vente de biens"
            ),
        }

        env = _get_jinja_env()
        html_string = env.get_template("supplier_invoice.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(None, _render_pdf_sync, html_string, base_url)
        logger.info("render_supplier_invoice_pdf_success", public_id=public_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_supplier_invoice_pdf_error", public_id=public_id, garage_id=garage_id)
        raise


async def render_credit_note_pdf(
    db: AsyncSession, *, credit_note_id: int, garage_id: int, redis: Redis
) -> bytes:
    """Fetch the credit note and its linked invoice, render HTML template, return PDF bytes."""
    logger.info("render_credit_note_pdf_start", credit_note_id=credit_note_id, garage_id=garage_id)
    try:
        cn = await credit_note_repo.get_credit_note_by_id(db, credit_note_id, garage_id)
        if cn is None:
            raise ValueError(f"Credit note {credit_note_id} not found")

        invoice = await invoice_repo.get_by_id(db, cn.invoice_id, garage_id)
        customer = None
        if invoice:
            customer = await customer_repo.get_by_id(db, garage_id, invoice.customer_id)

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": cn,
            "invoice": invoice,
            "customer": customer,
            "nature_of_operation": _nature_of_operation(invoice.lines) if invoice else None,
        }

        env = _get_jinja_env()
        html_string = env.get_template("credit_note.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(
            None, _render_pdf_sync, html_string, base_url
        )
        logger.info("render_credit_note_pdf_success", credit_note_id=credit_note_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_credit_note_pdf_error", credit_note_id=credit_note_id, garage_id=garage_id)
        raise


async def render_bon_de_retour_pdf(
    db: AsyncSession, *, public_id: str, garage_id: int, redis: Redis
) -> bytes:
    """Fetch bon de retour, resolve party (supplier or customer), render PDF."""
    from sqlalchemy import select
    from app.modules.bon_de_retour.repository import get_by_public_id
    from app.modules.supplier.models import Supplier

    logger.info("render_bon_de_retour_pdf_start", public_id=public_id, garage_id=garage_id)
    try:
        bdr = await get_by_public_id(db, public_id, garage_id)
        if bdr is None:
            raise ValueError(f"Bon de retour {public_id} not found")

        party_val = getattr(bdr.party_type, "value", bdr.party_type)
        customer = None
        supplier = None
        if party_val == "client" and bdr.customer_id:
            customer = await customer_repo.get_by_id(db, garage_id, bdr.customer_id)
        elif bdr.supplier_id:
            sup_res = await db.execute(select(Supplier).where(Supplier.id == bdr.supplier_id))
            supplier = sup_res.scalar_one_or_none()

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": bdr,
            "customer": customer,
            "supplier": supplier,
            "is_supplier": party_val == "supplier",
            "status_display": getattr(bdr.status, "value", bdr.status),
        }

        env = _get_jinja_env()
        html_string = env.get_template("bon_de_retour.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(None, _render_pdf_sync, html_string, base_url)
        logger.info("render_bon_de_retour_pdf_success", public_id=public_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_bon_de_retour_pdf_error", public_id=public_id, garage_id=garage_id)
        raise


async def render_advance_payment_pdf(
    db: AsyncSession, *, advance_id: int, garage_id: int, redis: Redis
) -> bytes:
    """Fetch the advance payment from DB, render HTML receipt template, return PDF bytes."""
    from app.modules.advance_payment import repository as advance_repo
    from app.modules.payment.models import PaymentMethod

    _PAYMENT_METHOD_LABELS: dict[PaymentMethod, str] = {
        PaymentMethod.cash: "Espèces",
        PaymentMethod.card: "Carte bancaire",
        PaymentMethod.bank_transfer: "Virement bancaire",
        PaymentMethod.cheque: "Chèque",
        PaymentMethod.other: "Autre",
    }

    logger.info("render_advance_payment_pdf_start", advance_id=advance_id, garage_id=garage_id)
    try:
        advance = await advance_repo.get_by_id(db, advance_id, garage_id)
        if advance is None:
            raise ValueError(f"Advance payment {advance_id} not found")

        customer = await customer_repo.get_by_id(db, garage_id, advance.customer_id)

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": advance,
            "customer": customer,
            "payment_method_label": _PAYMENT_METHOD_LABELS.get(advance.payment_method, advance.payment_method.value),
        }

        env = _get_jinja_env()
        html_string = env.get_template("advance_payment.html").render(**ctx)
        base_url = str(_TEMPLATES_DIR) + "/"

        loop = asyncio.get_event_loop()
        pdf_bytes: bytes = await loop.run_in_executor(
            None, _render_pdf_sync, html_string, base_url
        )
        logger.info("render_advance_payment_pdf_success", advance_id=advance_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except Exception:
        logger.exception("render_advance_payment_pdf_error", advance_id=advance_id, garage_id=garage_id)
        raise


async def render_invoice_pdf(
    db: AsyncSession, *, invoice_id: int, garage_id: int, redis: Redis
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

        ctx: dict[str, Any] = {
            **await _garage_context(db, redis, garage_id),
            "doc": invoice,
            "customer": customer,
            "vehicle": vehicle,
            "nature_of_operation": _nature_of_operation(invoice.lines),
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
