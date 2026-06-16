"""
Journal CSV formatters for each supported accounting software.

Formats:
- generic_csv : plain comma-separated, UTF-8
- sage        : semicolon-separated, French PCG accounts, DD/MM/YYYY dates
- cegid       : tab-separated, French PCG accounts, YYYY-MM-DD dates
- ebp         : semicolon-separated, same columns as Sage, slightly different labels

All monetary values are expressed in euros (minor-unit integers ÷ 100),
formatted as "1234.56" (generic) or "1234,56" (Sage/EBP/Cegid).
"""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Any


# ---------------------------------------------------------------------------
# Account codes (French Plan Comptable Général)
# ---------------------------------------------------------------------------
_ACC_CLIENT = "411000"
_ACC_REVENUE_SERVICE = "706000"
_ACC_REVENUE_GOODS = "707000"
_ACC_VAT_COLLECTED = "445710"
_ACC_SUPPLIER = "401000"
_ACC_PURCHASES = "607000"
_ACC_VAT_DEDUCTIBLE = "445660"
_ACC_BANK = "512000"
_ACC_CASH = "530000"

_PAYMENT_METHOD_TO_ACCOUNT = {
    "cash": _ACC_CASH,
    "card": _ACC_BANK,
    "bank_transfer": _ACC_BANK,
    "cheque": _ACC_BANK,
    "other": _ACC_BANK,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _eur(minor: int, decimal_sep: str = ".") -> str:
    s = f"{minor / 100:.2f}"
    if decimal_sep == ",":
        s = s.replace(".", ",")
    return s


def _date_fr(iso: str) -> str:
    """YYYY-MM-DD → DD/MM/YYYY."""
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


# ---------------------------------------------------------------------------
# Generic CSV — four sheets (invoices, payments, supplier invoices, VAT)
# ---------------------------------------------------------------------------


def _generic_sales_csv(invoices: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Document", "Client", "Base HT (€)", "TVA (€)", "Total TTC (€)"])
    for inv in invoices:
        w.writerow([
            inv["issued_at"],
            inv["doc_number"],
            inv["customer_name"],
            _eur(inv["amount_ht"]),
            _eur(inv["vat_amount"]),
            _eur(inv["amount_ttc"]),
        ])
    return buf.getvalue()


def _generic_payments_csv(payments: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Facture", "Client", "Moyen", "Montant (€)"])
    for pay in payments:
        w.writerow([
            pay["paid_at"],
            pay["doc_number"],
            pay["customer_name"],
            pay["method"],
            _eur(pay["amount_minor"]),
        ])
    return buf.getvalue()


def _generic_purchases_csv(
    supplier_invoices: list[dict[str, Any]],
    supplier_credit_notes: list[dict[str, Any]] | None = None,
) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "N° Document", "Type", "Fournisseur", "Base HT (€)", "TVA (€)", "Total TTC (€)"])
    for si in supplier_invoices:
        w.writerow([
            si["received_at"],
            si["number"],
            "Facture",
            si["supplier_name"],
            _eur(si["total_ht"]),
            _eur(si["vat_amount"]),
            _eur(si["total_ttc"]),
        ])
    for scn in (supplier_credit_notes or []):
        w.writerow([
            str(scn["issued_at"]),
            scn["doc_number"] or "AF",
            "Avoir",
            scn["supplier_name"],
            _eur(-scn["total_ht"]),
            _eur(-scn["vat_amount"]),
            _eur(-scn["total_ttc"]),
        ])
    return buf.getvalue()


def _generic_vat_csv(vat_summary: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Taux TVA",
        "Base HT ventes (€)",
        "TVA collectée (€)",
        "Base HT achats (€)",
        "TVA déductible (€)",
    ])
    for row in vat_summary:
        w.writerow([
            f"{row['vat_rate']:.1f}%",
            _eur(row["sales_base_ht"]),
            _eur(row["vat_collected"]),
            _eur(row["purchases_base_ht"]),
            _eur(row["vat_deductible"]),
        ])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# French-style journal line writer (Sage / EBP / Cegid share the same layout)
# ---------------------------------------------------------------------------


def _journal_header() -> list[str]:
    return ["Journal", "Date", "Pièce", "Compte", "Libellé", "Débit", "Crédit"]


def _journal_rows_sales(
    invoices: list[dict[str, Any]],
    date_fn,
    dec_sep: str,
) -> list[list[str]]:
    rows = []
    for inv in invoices:
        dt = date_fn(inv["issued_at"])
        doc = inv["doc_number"]
        client = inv["customer_name"][:35]
        ht = _eur(inv["amount_ht"], dec_sep)
        vat = _eur(inv["vat_amount"], dec_sep)
        ttc = _eur(inv["amount_ttc"], dec_sep)
        zero = _eur(0, dec_sep)
        rows += [
            ["VTE", dt, doc, _ACC_CLIENT, f"Client {client}", zero, ttc],
            ["VTE", dt, doc, _ACC_REVENUE_SERVICE, "Prestations de services", ht, zero],
            ["VTE", dt, doc, _ACC_VAT_COLLECTED, "TVA collectée", vat, zero],
        ]
    return rows


def _journal_rows_payments(
    payments: list[dict[str, Any]],
    date_fn,
    dec_sep: str,
) -> list[list[str]]:
    rows = []
    for pay in payments:
        dt = date_fn(pay["paid_at"])
        doc = pay["doc_number"]
        client = pay["customer_name"][:35]
        amount = _eur(pay["amount_minor"], dec_sep)
        zero = _eur(0, dec_sep)
        bank_acc = _PAYMENT_METHOD_TO_ACCOUNT.get(pay["method"], _ACC_BANK)
        rows += [
            ["BQ", dt, doc, _ACC_CLIENT, f"Client {client}", amount, zero],
            ["BQ", dt, doc, bank_acc, "Règlement", zero, amount],
        ]
    return rows


def _journal_rows_purchases(
    supplier_invoices: list[dict[str, Any]],
    date_fn,
    dec_sep: str,
) -> list[list[str]]:
    rows = []
    for si in supplier_invoices:
        dt = date_fn(si["received_at"])
        doc = si["number"][:35]
        sup = si["supplier_name"][:35]
        ht = _eur(si["total_ht"], dec_sep)
        vat = _eur(si["vat_amount"], dec_sep)
        ttc = _eur(si["total_ttc"], dec_sep)
        zero = _eur(0, dec_sep)
        rows += [
            ["ACH", dt, doc, _ACC_PURCHASES, "Achats de marchandises", ht, zero],
            ["ACH", dt, doc, _ACC_VAT_DEDUCTIBLE, "TVA déductible", vat, zero],
            ["ACH", dt, doc, _ACC_SUPPLIER, f"Fournisseur {sup}", zero, ttc],
        ]
    return rows


def _journal_rows_supplier_credit_notes(
    scns: list[dict[str, Any]],
    date_fn,
    dec_sep: str,
) -> list[list[str]]:
    """Reverse-purchase journal rows for supplier credit notes (avoirs fournisseur).

    Accounting entry (mirrors the SI reversal):
      Debit  401 (Fournisseurs)       — reduces supplier payable
      Credit 607 (Achats)             — reverses purchase cost
      Credit 445660 (TVA déductible)  — reverses deductible VAT
    """
    rows = []
    for scn in scns:
        dt = date_fn(str(scn["issued_at"]))
        doc = (scn["doc_number"] or "AF")[:35]
        sup = scn["supplier_name"][:35]
        ht = _eur(scn["total_ht"], dec_sep)
        vat = _eur(scn["vat_amount"], dec_sep)
        ttc = _eur(scn["total_ttc"], dec_sep)
        zero = _eur(0, dec_sep)
        rows += [
            ["ACH", dt, doc, _ACC_SUPPLIER, f"Fournisseur {sup}", ttc, zero],
            ["ACH", dt, doc, _ACC_PURCHASES, "Retour achats", zero, ht],
            ["ACH", dt, doc, _ACC_VAT_DEDUCTIBLE, "TVA déductible", zero, vat],
        ]
    return rows


def _write_journal_csv(rows: list[list[str]], sep: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep)
    w.writerow(_journal_header())
    w.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Format-specific builders
# ---------------------------------------------------------------------------


def _build_sage(
    invoices: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    supplier_invoices: list[dict[str, Any]],
    vat_summary: list[dict[str, Any]],
    supplier_credit_notes: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    sep = ";"
    date_fn = _date_fr
    dec = ","
    achats_rows = _journal_rows_purchases(supplier_invoices, date_fn, dec) + \
                  _journal_rows_supplier_credit_notes(supplier_credit_notes or [], date_fn, dec)
    return {
        "journal_ventes.csv": _write_journal_csv(_journal_rows_sales(invoices, date_fn, dec), sep),
        "journal_reglements.csv": _write_journal_csv(_journal_rows_payments(payments, date_fn, dec), sep),
        "journal_achats.csv": _write_journal_csv(achats_rows, sep),
        "balance_tva.csv": _generic_vat_csv(vat_summary),
    }


def _build_cegid(
    invoices: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    supplier_invoices: list[dict[str, Any]],
    vat_summary: list[dict[str, Any]],
    supplier_credit_notes: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    sep = "\t"
    date_fn = lambda iso: iso  # noqa: E731 — ISO already YYYY-MM-DD
    dec = ","
    achats_rows = _journal_rows_purchases(supplier_invoices, date_fn, dec) + \
                  _journal_rows_supplier_credit_notes(supplier_credit_notes or [], date_fn, dec)
    return {
        "journal_ventes.csv": _write_journal_csv(_journal_rows_sales(invoices, date_fn, dec), sep),
        "journal_reglements.csv": _write_journal_csv(_journal_rows_payments(payments, date_fn, dec), sep),
        "journal_achats.csv": _write_journal_csv(achats_rows, sep),
        "balance_tva.csv": _generic_vat_csv(vat_summary),
    }


def _build_ebp(
    invoices: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    supplier_invoices: list[dict[str, Any]],
    vat_summary: list[dict[str, Any]],
    supplier_credit_notes: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    sep = ";"
    date_fn = _date_fr
    dec = ","
    achats_rows = _journal_rows_purchases(supplier_invoices, date_fn, dec) + \
                  _journal_rows_supplier_credit_notes(supplier_credit_notes or [], date_fn, dec)
    return {
        "journal_ventes.csv": _write_journal_csv(_journal_rows_sales(invoices, date_fn, dec), sep),
        "journal_reglements.csv": _write_journal_csv(_journal_rows_payments(payments, date_fn, dec), sep),
        "journal_achats.csv": _write_journal_csv(achats_rows, sep),
        "balance_tva.csv": _generic_vat_csv(vat_summary),
    }


def _build_generic_csv(
    invoices: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    supplier_invoices: list[dict[str, Any]],
    vat_summary: list[dict[str, Any]],
    supplier_credit_notes: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    return {
        "journal_ventes.csv": _generic_sales_csv(invoices),
        "journal_reglements.csv": _generic_payments_csv(payments),
        "journal_achats.csv": _generic_purchases_csv(supplier_invoices, supplier_credit_notes),
        "balance_tva.csv": _generic_vat_csv(vat_summary),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_BUILDERS = {
    "sage": _build_sage,
    "cegid": _build_cegid,
    "ebp": _build_ebp,
    "generic_csv": _build_generic_csv,
}


def generate_zip(
    fmt: str,
    invoices: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    supplier_invoices: list[dict[str, Any]],
    vat_summary: list[dict[str, Any]],
    supplier_credit_notes: list[dict[str, Any]] | None = None,
) -> bytes:
    """Return a ZIP archive containing the journal CSV files for the given format."""
    builder = _BUILDERS.get(fmt, _build_generic_csv)
    files = builder(invoices, payments, supplier_invoices, vat_summary, supplier_credit_notes)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content.encode("utf-8-sig"))  # UTF-8 BOM for Excel compat
    return buf.getvalue()
