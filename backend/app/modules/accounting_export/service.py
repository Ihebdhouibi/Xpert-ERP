"""Accounting export — business logic."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.accounting_export.formatters import generate_zip
from app.modules.accounting_export.models import AccountingExport
from app.modules.accounting_export.repository import AccountingExportRepository


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class AccountingExportNotFoundError(Exception):
    pass


class AccountingExportInvalidFormatError(Exception):
    pass


# ---------------------------------------------------------------------------
# Data gathering helpers
# ---------------------------------------------------------------------------

_VALID_FORMATS = {"sage", "cegid", "ebp", "generic_csv"}


async def _gather_invoices(
    db: AsyncSession, garage_id: int, period_start: str, period_end: str
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT
                i.id,
                i.doc_number,
                DATE(i.issued_at) AS issued_at,
                c.full_name AS customer_name,
                i.subtotal_minor AS amount_ht,
                i.vat_minor AS vat_amount,
                i.total_minor AS amount_ttc,
                i.is_exported
            FROM invoice i
            JOIN customer c ON c.id = i.customer_id
            WHERE i.garage_id = :g
              AND i.status IN ('issued', 'partial', 'paid')
              AND i.deleted_at IS NULL
              AND DATE(i.issued_at) >= :ps
              AND DATE(i.issued_at) <= :pe
            ORDER BY i.issued_at
            """
        ),
        {"g": garage_id, "ps": period_start, "pe": period_end},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def _gather_payments(
    db: AsyncSession, garage_id: int, period_start: str, period_end: str
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT
                p.id,
                i.doc_number,
                DATE(p.paid_at) AS paid_at,
                c.full_name AS customer_name,
                p.payment_method AS method,
                p.amount_minor,
                p.is_exported
            FROM payment p
            JOIN invoice i ON i.id = p.invoice_id
            JOIN customer c ON c.id = i.customer_id
            WHERE p.garage_id = :g
              AND i.deleted_at IS NULL
              AND DATE(p.paid_at) >= :ps
              AND DATE(p.paid_at) <= :pe
            ORDER BY p.paid_at
            """
        ),
        {"g": garage_id, "ps": period_start, "pe": period_end},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def _gather_supplier_invoices(
    db: AsyncSession, garage_id: int, period_start: str, period_end: str
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT
                si.id,
                si.number,
                DATE(si.received_at) AS received_at,
                s.name AS supplier_name,
                si.total_ht,
                si.total_ttc - si.total_ht AS vat_amount,
                si.total_ttc,
                si.is_exported
            FROM supplier_invoice si
            JOIN supplier s ON s.id = si.supplier_id
            WHERE si.garage_id = :g
              AND si.status IN ('approved', 'paid')
              AND si.deleted_at IS NULL
              AND DATE(si.received_at) >= :ps
              AND DATE(si.received_at) <= :pe
            ORDER BY si.received_at
            """
        ),
        {"g": garage_id, "ps": period_start, "pe": period_end},
    )
    return [dict(row._mapping) for row in result.fetchall()]


def _build_vat_summary(
    invoices: list[dict[str, Any]],
    supplier_invoices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate VAT by rate from invoices and supplier invoices.

    Since we don't store per-rate VAT breakdowns at the invoice level, we use
    the blended rate as a single bucket (standard French 20% applies to most).
    This produces one row per distinct effective VAT rate found.
    """
    sales: dict[str, dict[str, int]] = {}
    for inv in invoices:
        ht = inv["amount_ht"]
        vat = inv["vat_amount"]
        if ht > 0:
            rate_key = f"{round(vat / ht * 100, 1):.1f}" if ht else "0.0"
        else:
            rate_key = "0.0"
        bucket = sales.setdefault(rate_key, {"sales_base_ht": 0, "vat_collected": 0})
        bucket["sales_base_ht"] += ht
        bucket["vat_collected"] += vat

    purchases: dict[str, dict[str, int]] = {}
    for si in supplier_invoices:
        ht = si["total_ht"]
        vat = si["vat_amount"]
        if ht > 0:
            rate_key = f"{round(vat / ht * 100, 1):.1f}" if ht else "0.0"
        else:
            rate_key = "0.0"
        bucket = purchases.setdefault(rate_key, {"purchases_base_ht": 0, "vat_deductible": 0})
        bucket["purchases_base_ht"] += ht
        bucket["vat_deductible"] += vat

    all_rates = sorted(set(sales) | set(purchases))
    return [
        {
            "vat_rate": float(r),
            "sales_base_ht": sales.get(r, {}).get("sales_base_ht", 0),
            "vat_collected": sales.get(r, {}).get("vat_collected", 0),
            "purchases_base_ht": purchases.get(r, {}).get("purchases_base_ht", 0),
            "vat_deductible": purchases.get(r, {}).get("vat_deductible", 0),
        }
        for r in all_rates
    ]


async def _mark_exported(
    db: AsyncSession,
    garage_id: int,
    invoice_ids: list[int],
    payment_ids: list[int],
    si_ids: list[int],
) -> None:
    from sqlalchemy import update as sa_update
    from app.modules.invoice.models import Invoice
    from app.modules.payment.models import Payment
    from app.modules.supplier_invoice.models import SupplierInvoice

    if invoice_ids:
        await db.execute(
            sa_update(Invoice)
            .where(Invoice.garage_id == garage_id, Invoice.id.in_(invoice_ids))
            .values(is_exported=True)
        )
    if payment_ids:
        await db.execute(
            sa_update(Payment)
            .where(Payment.garage_id == garage_id, Payment.id.in_(payment_ids))
            .values(is_exported=True)
        )
    if si_ids:
        await db.execute(
            sa_update(SupplierInvoice)
            .where(SupplierInvoice.garage_id == garage_id, SupplierInvoice.id.in_(si_ids))
            .values(is_exported=True)
        )


# ---------------------------------------------------------------------------
# Period preview (re-export detection)
# ---------------------------------------------------------------------------


async def preview_export(
    db: AsyncSession,
    garage_id: int,
    period_start: str,
    period_end: str,
) -> dict[str, int]:
    """Return counts of pending and already-exported records in the period."""
    invoices = await _gather_invoices(db, garage_id, period_start, period_end)
    payments = await _gather_payments(db, garage_id, period_start, period_end)
    sis = await _gather_supplier_invoices(db, garage_id, period_start, period_end)

    return {
        "already_exported_invoices": sum(1 for r in invoices if r["is_exported"]),
        "already_exported_payments": sum(1 for r in payments if r["is_exported"]),
        "already_exported_supplier_invoices": sum(1 for r in sis if r["is_exported"]),
        "pending_invoices": sum(1 for r in invoices if not r["is_exported"]),
        "pending_payments": sum(1 for r in payments if not r["is_exported"]),
        "pending_supplier_invoices": sum(1 for r in sis if not r["is_exported"]),
    }


# ---------------------------------------------------------------------------
# Create / run export
# ---------------------------------------------------------------------------


async def create_export(
    db: AsyncSession,
    garage_id: int,
    period_start: str,
    period_end: str,
    fmt: Optional[str],
    user_id: Optional[int],
) -> AccountingExport:
    settings = get_settings()
    resolved_fmt = fmt or settings.cfg_accounting_format
    if resolved_fmt not in _VALID_FORMATS:
        raise AccountingExportInvalidFormatError(
            f"Unknown format '{resolved_fmt}'. Valid values: {sorted(_VALID_FORMATS)}"
        )

    export = await AccountingExportRepository.create(
        db,
        garage_id=garage_id,
        period_start=period_start,
        period_end=period_end,
        format=resolved_fmt,
        exported_by=user_id,
    )

    try:
        invoices = await _gather_invoices(db, garage_id, period_start, period_end)
        payments = await _gather_payments(db, garage_id, period_start, period_end)
        sis = await _gather_supplier_invoices(db, garage_id, period_start, period_end)

        # Only export records not yet exported
        pending_invoices = [r for r in invoices if not r["is_exported"]]
        pending_payments = [r for r in payments if not r["is_exported"]]
        pending_sis = [r for r in sis if not r["is_exported"]]

        vat_summary = _build_vat_summary(pending_invoices, pending_sis)
        zip_bytes = generate_zip(resolved_fmt, pending_invoices, pending_payments, pending_sis, vat_summary)

        # Store to S3
        storage_key = (
            f"accounting_exports/{garage_id}/"
            f"{period_start}_{period_end}_{resolved_fmt}_{export.public_id}.zip"
        )
        from app.modules.documents.storage import upload_bytes

        await upload_bytes(
            bucket=settings.s3_bucket_documents,
            key=storage_key,
            data=zip_bytes,
            content_type="application/zip",
        )

        # Mark records as exported
        await _mark_exported(
            db,
            garage_id,
            invoice_ids=[r["id"] for r in pending_invoices],
            payment_ids=[r["id"] for r in pending_payments],
            si_ids=[r["id"] for r in pending_sis],
        )

        export = await AccountingExportRepository.update(
            db,
            export,
            status="completed",
            file_storage_key=storage_key,
            exported_at=datetime.now(timezone.utc),
            record_counts={
                "invoices": len(pending_invoices),
                "payments": len(pending_payments),
                "supplier_invoices": len(pending_sis),
            },
        )
        await db.commit()

    except Exception as exc:
        await db.rollback()
        # Persist failure status in a new transaction
        from app.core.database import AsyncSessionFactory

        async with AsyncSessionFactory() as err_db:
            failed_export = await AccountingExportRepository.get_by_public_id(
                err_db, garage_id, str(export.public_id)
            )
            if failed_export:
                await AccountingExportRepository.update(
                    err_db,
                    failed_export,
                    status="failed",
                    error_message=str(exc)[:500],
                )
                await err_db.commit()
        raise

    return export


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


async def list_exports(
    db: AsyncSession,
    garage_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AccountingExport], int]:
    return await AccountingExportRepository.list(db, garage_id, page, page_size)


async def get_export(
    db: AsyncSession, garage_id: int, public_id: str
) -> AccountingExport:
    obj = await AccountingExportRepository.get_by_public_id(db, garage_id, public_id)
    if not obj:
        raise AccountingExportNotFoundError(public_id)
    return obj


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


async def get_download_url(
    db: AsyncSession, garage_id: int, public_id: str
) -> str:
    obj = await get_export(db, garage_id, public_id)
    if not obj.file_storage_key:
        raise AccountingExportNotFoundError("Export file not available")

    settings = get_settings()
    from app.modules.documents.storage import generate_presigned_url

    return await generate_presigned_url(
        bucket=settings.s3_bucket_documents,
        key=obj.file_storage_key,
        expiry_seconds=settings.signed_url_expiry_seconds,
    )
