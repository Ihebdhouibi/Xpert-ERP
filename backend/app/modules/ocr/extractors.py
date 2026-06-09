"""Structured field extractors for specific document categories.

Each extractor receives a :class:`~app.modules.ocr.engine.RawOcrResult` and
returns a mapping of ``field_name → (value, confidence)``.

Design rules:
- Extractors MUST NOT write to any DB table.
- Confidence values reflect the OCR engine's line confidence; layout heuristics
  may lower but never raise the engine confidence.
- Fields that cannot be found are omitted from the returned dict.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from app.modules.ocr.engine import RawOcrResult

# Type alias: field → (extracted_value, confidence)
FieldMap = dict[str, tuple[str, float]]


# ---------------------------------------------------------------------------
# Carte grise (registration card) — Moroccan / French format
# ---------------------------------------------------------------------------

# Patterns for common registration card fields
_RE_IMMATRICULATION = re.compile(
    r"\b(\d{1,5}[-\s]?[A-Z]{1,3}[-\s]?\d{1,2})\b"  # Moroccan: 12345-AB-06
    r"|\b([A-Z]{2}[-\s]?\d{3}[-\s]?[A-Z]{2})\b",  # French SIV: AB-123-CD
    re.IGNORECASE,
)
_RE_VIN = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b", re.IGNORECASE)
_RE_DATE = re.compile(r"\b(\d{2}[./\-]\d{2}[./\-]\d{2,4})\b")

# Keyword markers that precede the fields on the document
_KW_PROPRIETAIRE = re.compile(r"propri[eé]taire|titulaire|nom", re.IGNORECASE)
_KW_MARQUE = re.compile(r"\bmarque\b|\bD\.1\b", re.IGNORECASE)
_KW_MODELE = re.compile(r"\bmod[eè]le\b|\bD\.3\b|\btype\b", re.IGNORECASE)
_KW_DATE_MEC = re.compile(r"1[eè]re\s+immatriculation|mise\s+en\s+circulation|date\s+d.immatriculation|B\b", re.IGNORECASE)


def _best_line_after_keyword(lines, keyword_re: re.Pattern) -> Optional[tuple[str, float]]:
    """Return the text+confidence of the first non-keyword line that follows a keyword line."""
    found_kw = False
    for line in lines:
        if found_kw and line.text.strip():
            return line.text.strip(), line.confidence
        if keyword_re.search(line.text):
            found_kw = True
    return None


def extract_carte_grise(result: RawOcrResult) -> FieldMap:
    """Extract structured fields from a Carte Grise (registration card) OCR result."""
    fields: FieldMap = {}
    lines = result.lines

    # Immatriculation — scan all lines for the pattern; pick highest confidence
    best_immat: Optional[tuple[str, float]] = None
    for line in lines:
        m = _RE_IMMATRICULATION.search(line.text)
        if m:
            val = (m.group(1) or m.group(2) or "").upper().replace(" ", "-")
            if best_immat is None or line.confidence > best_immat[1]:
                best_immat = (val, line.confidence)
    if best_immat:
        fields["immatriculation"] = best_immat

    # VIN
    for line in lines:
        m = _RE_VIN.search(line.text)
        if m:
            fields["vin"] = (m.group(1).upper(), line.confidence)
            break

    # Date mise en circulation
    for line in lines:
        if _KW_DATE_MEC.search(line.text):
            m = _RE_DATE.search(line.text)
            if m:
                fields["date_mise_en_circulation"] = (m.group(1), line.confidence)
                break
            # value might be on the next line
            result_next = _best_line_after_keyword(lines, _KW_DATE_MEC)
            if result_next:
                m2 = _RE_DATE.search(result_next[0])
                if m2:
                    fields["date_mise_en_circulation"] = (m2.group(1), result_next[1])
            break

    # Marque
    after_marque = _best_line_after_keyword(lines, _KW_MARQUE)
    if after_marque:
        fields["marque"] = after_marque

    # Modele
    after_modele = _best_line_after_keyword(lines, _KW_MODELE)
    if after_modele:
        fields["modele"] = after_modele

    # Propriétaire
    after_prop = _best_line_after_keyword(lines, _KW_PROPRIETAIRE)
    if after_prop:
        fields["proprietaire"] = after_prop

    return fields


# ---------------------------------------------------------------------------
# Carte Nationale d'Identité (CIN) — Moroccan format
# ---------------------------------------------------------------------------

_RE_CIN = re.compile(r"\b([A-Z]{1,2}\d{5,6})\b", re.IGNORECASE)
_RE_BIRTH_DATE = re.compile(r"\b(\d{2}[./\-]\d{2}[./\-]\d{4})\b")

_KW_NOM = re.compile(r"\bnom\b|\bسم\b", re.IGNORECASE)
_KW_PRENOM = re.compile(r"\bpr[eé]nom\b|\bالإسم\b", re.IGNORECASE)
_KW_DATE_NAISS = re.compile(r"n[eé]\s*(le|à)?\b|date.*naissance|تاريخ.*الازد", re.IGNORECASE)
_KW_CIN_LABEL = re.compile(r"\bCIN\b|\bcarte\s+nationale\b|\bIdentit[eé]\b", re.IGNORECASE)


def extract_national_id(result: RawOcrResult) -> FieldMap:
    """Extract structured fields from a Moroccan CIN OCR result."""
    fields: FieldMap = {}
    lines = result.lines

    # CIN number
    for line in lines:
        m = _RE_CIN.search(line.text)
        if m:
            fields["numero_cin"] = (m.group(1).upper(), line.confidence)
            break

    # Nom
    after_nom = _best_line_after_keyword(lines, _KW_NOM)
    if after_nom:
        fields["nom"] = after_nom

    # Prénom
    after_prenom = _best_line_after_keyword(lines, _KW_PRENOM)
    if after_prenom:
        fields["prenom"] = after_prenom

    # Date de naissance
    for line in lines:
        if _KW_DATE_NAISS.search(line.text):
            m = _RE_BIRTH_DATE.search(line.text)
            if m:
                fields["date_naissance"] = (m.group(1), line.confidence)
                break
            after_date = _best_line_after_keyword(lines, _KW_DATE_NAISS)
            if after_date:
                m2 = _RE_BIRTH_DATE.search(after_date[0])
                if m2:
                    fields["date_naissance"] = (m2.group(1), after_date[1])
            break

    return fields


# ---------------------------------------------------------------------------
# Invoices — customer invoice (facture) & supplier invoice (facture fournisseur)
# ---------------------------------------------------------------------------

# A monetary amount in French format: 1 234,56 / 1.234,56 / 1234.56 / 99,00
_RE_AMOUNT = re.compile(r"\b(\d{1,3}(?:[ .]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2})\b")
# Day/month may be single- or double-digit (e.g. 2.6.2021 or 02/06/2021)
_RE_DATE_ANY = re.compile(r"\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\b")
# A line that looks like a description followed by qty / unit price / total
_RE_LINE_ITEM = re.compile(
    r"^(?P<desc>.+?)\s+(?P<qty>\d{1,4})\s+(?P<unit>\d{1,3}(?:[ .]\d{3})*[.,]\d{2})"
    r"(?:\s+(?P<total>\d{1,3}(?:[ .]\d{3})*[.,]\d{2}))?\s*$"
)

_KW_DATE_FACTURE = re.compile(r"date\s*(de)?\s*facture|date\s*d.[ée]mission|invoice\s*date", re.IGNORECASE)
_KW_DATE_ECHEANCE = re.compile(r"[ée]ch[ée]ance|date\s*limite|due\s*date|paiement\s*avant", re.IGNORECASE)
_KW_TOTAL_HT = re.compile(
    r"total\s*h\.?\s*t\.?|montant\s*h\.?\s*t\.?|sous[- ]?total|bases?\s*h\.?\s*t\.?|^\s*h\.?\s*t\.?\s*[:.]",
    re.IGNORECASE,
)
_KW_TOTAL_TTC = re.compile(r"total\s*t\.?t\.?c\.?|net\s*[àa]\s*payer|montant\s*[àa]\s*payer", re.IGNORECASE)
_KW_TVA = re.compile(r"\bt\.?v\.?a\.?\b|taxe", re.IGNORECASE)
_KW_FOURNISSEUR = re.compile(r"fournisseur|[ée]metteur|vendeur|raison\s*sociale", re.IGNORECASE)
_KW_CLIENT = re.compile(r"\bclient\b|destinataire|factur[ée]\s*[àa]|adress[ée]\s*[àa]", re.IGNORECASE)

# Invoice-number heuristics — robust to table/collapsed layouts where the label
# and value share a line (e.g. "facture en € n° : 10003567").
_RE_NUM_TOKEN = re.compile(r"\b([A-Z0-9][A-Z0-9\-/]{2,})\b", re.IGNORECASE)
_RE_IS_DATE = re.compile(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}")
_KW_INV_LINE = re.compile(r"facture|invoice", re.IGNORECASE)
_KW_NUM_LINE = re.compile(r"num[ée]ro|n[°ºo]", re.IGNORECASE)
# Lines whose numbers are NOT the invoice number (amounts, taxes, ids).
_KW_EXCLUDE_NUM = re.compile(
    r"total|tva|acompte|ttc|\bht\b|net\s*[àa]\s*payer|base|siret|iban", re.IGNORECASE
)


def _first_code_with_digit(text: str) -> Optional[str]:
    """Return the first token that contains a digit and isn't a date."""
    for m in _RE_NUM_TOKEN.finditer(text):
        tok = m.group(1)
        if not any(c.isdigit() for c in tok):
            continue
        if _RE_IS_DATE.fullmatch(tok):
            continue
        return tok.upper()
    return None


def _extract_invoice_number(lines) -> Optional[tuple[str, float]]:
    """Find the invoice number: a code on a 'facture'/'n°' line (not an amount)."""
    for keyword in (_KW_INV_LINE, _KW_NUM_LINE):
        for line in lines:
            text = line.text
            if keyword.search(text) and not _KW_EXCLUDE_NUM.search(text):
                tok = _first_code_with_digit(text)
                if tok:
                    return tok, line.confidence
    return None


# Lines that mention a total in prose (a discount note, a rate) — their amounts
# are NOT the total. e.g. "Le Total HT tient compte d'une remise … soit 3.51%".
_KW_AMOUNT_SKIP = re.compile(r"remise|tient\s+compte|\bsoit\b", re.IGNORECASE)


def _amount_not_percent(text: str) -> Optional[str]:
    """First monetary amount in *text* that isn't immediately followed by '%'."""
    for m in _RE_AMOUNT.finditer(text):
        trailing = text[m.end():m.end() + 1]
        if trailing == "%":
            continue
        return m.group(1)
    return None


def _amount_on_keyword_line(lines, keyword_re: re.Pattern) -> Optional[tuple[str, float]]:
    """Find an amount on the first line matching ``keyword_re`` (or the next line).

    Skips prose lines (discount notes) and percentage values so a label like
    "Total HT" in a sentence doesn't capture a rate instead of the amount.
    """
    for idx, line in enumerate(lines):
        if keyword_re.search(line.text):
            if _KW_AMOUNT_SKIP.search(line.text):
                continue
            amt = _amount_not_percent(line.text)
            if amt:
                return _normalise_amount(amt), line.confidence
            # Amount may be on the following line
            if idx + 1 < len(lines):
                nxt = lines[idx + 1]
                amt2 = _amount_not_percent(nxt.text)
                if amt2:
                    return _normalise_amount(amt2), nxt.confidence
    return None


def _normalise_amount(raw: str) -> str:
    """Normalise a FR-formatted amount to a plain ``1234.56`` string."""
    s = raw.replace(" ", "")
    if "," in s:
        # comma is the decimal separator; dots are thousands separators
        s = s.replace(".", "").replace(",", ".")
    return s


def _extract_line_items(lines) -> Optional[tuple[str, float]]:
    """Best-effort line-item extraction, returned as a JSON-encoded string.

    Always low-confidence — invoice tables vary wildly, so these are a hint for
    the human reviewer, never an authoritative value.
    """
    items: list[dict] = []
    for line in lines:
        m = _RE_LINE_ITEM.match(line.text.strip())
        if not m:
            continue
        desc = m.group("desc").strip()
        # Skip rows that are clearly totals/headers
        if _KW_TOTAL_HT.search(desc) or _KW_TOTAL_TTC.search(desc) or _KW_TVA.search(desc):
            continue
        items.append(
            {
                "description": desc,
                "quantity": m.group("qty"),
                "unit_price": _normalise_amount(m.group("unit")),
                "line_total": _normalise_amount(m.group("total")) if m.group("total") else None,
            }
        )
    if not items:
        return None
    # Confidence kept deliberately low so the field is flagged needs_review.
    return json.dumps(items, ensure_ascii=False), 0.40


def _match_value(m: re.Match) -> str:
    return m.group(1) if m.groups() else m.group(0)


def _value_near_keyword(lines, keyword_re: re.Pattern, value_re: re.Pattern):
    """Find a value spatially associated with a keyword (structured/layout-aware).

    Order of preference: same line as the label, then the value directly *below*
    it (column header → value), then to its *right* (label : value). Uses the
    per-line bounding boxes so table cells are matched correctly.
    """
    kw_lines = [ln for ln in lines if keyword_re.search(ln.text)]
    # 1. Same line as the keyword
    for kw in kw_lines:
        m = value_re.search(kw.text)
        if m:
            return _match_value(m), kw.confidence
    # 2. Spatially nearest value below or to the right of any keyword line
    best = None
    best_score: Optional[float] = None
    for kw in kw_lines:
        if not kw.box:
            continue
        kx1, ky1, kx2, ky2 = kw.box
        kcx, kcy = (kx1 + kx2) / 2, (ky1 + ky2) / 2
        for cand in lines:
            if cand is kw or not cand.box:
                continue
            m = value_re.search(cand.text)
            if not m:
                continue
            cx1, cy1, cx2, cy2 = cand.box
            x_overlap = min(kx2, cx2) - max(kx1, cx1)
            y_overlap = min(ky2, cy2) - max(ky1, cy1)
            score: Optional[float] = None
            if cy1 >= ky2 - 4 and x_overlap > -8:           # value below the label
                score = (cy1 - ky2) + abs((cx1 + cx2) / 2 - kcx)
            elif cx1 >= kx2 - 4 and y_overlap > -4:          # value to the right
                score = (cx1 - kx2) + abs((cy1 + cy2) / 2 - kcy)
            if score is not None and (best_score is None or score < best_score):
                best_score = score
                best = (_match_value(m), cand.confidence)
    return best


def _extract_invoice_common(result: RawOcrResult, party_keyword: re.Pattern, party_field: str) -> FieldMap:
    """Shared header extraction for customer and supplier invoices."""
    fields: FieldMap = {}
    lines = result.lines

    # Invoice number
    numero = _extract_invoice_number(lines)
    if numero:
        fields["numero_facture"] = numero

    # Invoice date — labelled (layout-aware), else the first date in the document
    dfac = _value_near_keyword(lines, _KW_DATE_FACTURE, _RE_DATE_ANY)
    if dfac:
        fields["date_facture"] = dfac
    else:
        for line in lines:
            m = _RE_DATE_ANY.search(line.text)
            if m:
                fields["date_facture"] = (m.group(1), line.confidence)
                break

    # Due date — labelled (layout-aware): value is often in the cell below the label
    dech = _value_near_keyword(lines, _KW_DATE_ECHEANCE, _RE_DATE_ANY)
    if dech:
        fields["date_echeance"] = dech

    # Party (supplier or client)
    after_party = _best_line_after_keyword(lines, party_keyword)
    if after_party:
        fields[party_field] = after_party

    # Amounts
    ht = _amount_on_keyword_line(lines, _KW_TOTAL_HT)
    if ht:
        fields["total_ht"] = ht
    tva = _amount_on_keyword_line(lines, _KW_TVA)
    if tva:
        fields["tva"] = tva
    ttc = _amount_on_keyword_line(lines, _KW_TOTAL_TTC)
    if ttc:
        fields["total_ttc"] = ttc

    # Best-effort line items (JSON string, low confidence)
    items = _extract_line_items(lines)
    if items:
        fields["lignes"] = items

    return fields


def extract_invoice(result: RawOcrResult) -> FieldMap:
    """Extract structured fields from a customer-facing invoice (facture)."""
    return _extract_invoice_common(result, _KW_CLIENT, "client")


def extract_supplier_invoice(result: RawOcrResult) -> FieldMap:
    """Extract structured fields from a supplier invoice (facture fournisseur)."""
    return _extract_invoice_common(result, _KW_FOURNISSEUR, "fournisseur")
