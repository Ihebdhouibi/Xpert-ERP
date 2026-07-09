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
_KW_COULEUR = re.compile(r"\bcouleur\b|\bC\.2\b|\bcolor\b", re.IGNORECASE)


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

    # Date mise en circulation (field B on French/Tunisian registration cards).
    # OCR often splits the field code "B", the label "Date de 1ère immatriculation"
    # and the value "05/01/1998" across separate lines. We enumerate with an index
    # so we can look 1–2 lines ahead without re-scanning from the start (which was
    # the old bug: re-scanning returned the label line, not the date).
    for idx, line in enumerate(lines):
        if _KW_DATE_MEC.search(line.text):
            # Try the same line first (e.g. "B  05/01/1998" all on one line).
            m = _RE_DATE.search(line.text)
            if m:
                fields["date_mise_en_circulation"] = (m.group(1), line.confidence)
                break
            # Try the next 1–2 lines (label then value may be on separate lines).
            for offset in range(1, 3):
                if idx + offset < len(lines):
                    nxt = lines[idx + offset]
                    m2 = _RE_DATE.search(nxt.text)
                    if m2:
                        fields["date_mise_en_circulation"] = (m2.group(1), nxt.confidence)
                        break
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

    # Couleur (field C.2 on French/Tunisian registration cards)
    after_couleur = _best_line_after_keyword(lines, _KW_COULEUR)
    if after_couleur:
        fields["couleur"] = after_couleur

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
# Same, but never matches a percentage (e.g. the "3.51%" in a discount note).
_RE_AMOUNT_NO_PCT = re.compile(
    r"\b(\d{1,3}(?:[ .]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2})\b(?!\s*%)"
)
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
# The TVA *amount* label, excluding the "%T.V.A." rate column (whose value is the
# rate, e.g. 20,00 — not the tax amount). A leading "%" disqualifies the cell.
_KW_TVA_AMOUNT = re.compile(r"(?<!%)\bt\.?v\.?a\.?\b|taxe", re.IGNORECASE)
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


def _amount_near_keyword(
    lines, keyword_re: re.Pattern, band_y: Optional[float] = None, tol: float = 100
):
    """Layout-aware amount: the value physically nearest the label (below/right).

    When ``band_y`` is given, only label cells whose vertical centre is within
    ``tol`` of it are considered — this restricts matching to the totals band and
    ignores same-named column headers higher up the page (e.g. a "Montant HT"
    line-item header vs the grand "Total H.T." at the bottom).

    Kept in the document's own format (comma decimals). Falls back to the flat
    keyword-line scan when no spatial match is found — this is what makes totals
    work on exploded-cell tables where the amount is never on the label's line.
    """
    def cy(box):
        return (box[1] + box[3]) / 2

    kw_lines = [ln for ln in lines if keyword_re.search(ln.text)]
    if band_y is not None:
        kw_lines = [
            ln for ln in kw_lines if ln.box and abs(cy(ln.box) - band_y) <= tol
        ]

    # 1. Amount on the same line as the label.
    for kw in kw_lines:
        m = _RE_AMOUNT_NO_PCT.search(kw.text)
        if m:
            return _match_value(m), kw.confidence
    # 2. Spatially nearest amount below or to the right of any label line.
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
            m = _RE_AMOUNT_NO_PCT.search(cand.text)
            if not m:
                continue
            cx1, cy1, cx2, cy2 = cand.box
            x_overlap = min(kx2, cx2) - max(kx1, cx1)
            y_overlap = min(ky2, cy2) - max(ky1, cy1)
            score: Optional[float] = None
            if cy1 >= ky2 - 4 and x_overlap > -8:            # value below the label
                score = (cy1 - ky2) + abs((cx1 + cx2) / 2 - kcx)
            elif cx1 >= kx2 - 4 and y_overlap > -4:           # value to the right
                score = (cx1 - kx2) + abs((cy1 + cy2) / 2 - kcy)
            if score is not None and (best_score is None or score < best_score):
                best_score = score
                best = (_match_value(m), cand.confidence)
    if best:
        return best
    if band_y is None:
        return _amount_on_keyword_line(lines, keyword_re)
    return None


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

    # Fallback: derive TVA = TTC − HT when the keyword search found nothing.
    # Invoices often place the TVA amount in a table column where the label
    # ("TVA") and the value ("9.97") are on different OCR lines with no clean
    # pairing, so the pattern-based search misses it.
    if "tva" not in fields and "total_ttc" in fields and "total_ht" in fields:
        try:
            ttc_val = float(fields["total_ttc"][0])
            ht_val = float(fields["total_ht"][0])
            diff = round(ttc_val - ht_val, 2)
            if diff > 0:
                conf = round(min(fields["total_ttc"][1], fields["total_ht"][1]) * 0.95, 4)
                fields["tva"] = (f"{diff:.2f}", conf)
        except (TypeError, ValueError):
            pass

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


# ---------------------------------------------------------------------------
# Bon de livraison (supplier delivery note)
# ---------------------------------------------------------------------------

# BL number: a letter-prefixed code with >=3 digits (BL027543) or >=4 digits
# (24639). The >=4-digit floor avoids matching 3-digit amounts like "120".
_RE_BL_NUMBER = re.compile(r"\b([A-Z]{1,4}\d{3,}[A-Z0-9]*|\d{4,})\b", re.IGNORECASE)
# The BL number is the value under "N° de la pièce". The degree sign is optional
# because OCR frequently drops it ("N de la piece" / "Nde la piece").
_KW_BL_NUMBER = re.compile(
    r"bon\s*de\s*livraison|n[°ºo]?\s*de\s*la\s*pi[eè]ce|num[ée]ro|\bBL\b", re.IGNORECASE
)
_KW_DATE_BL = re.compile(r"date\s*(de\s*)?livraison|\bdate\b", re.IGNORECASE)
_KW_REF_COMMANDE = re.compile(
    r"r[ée]f[ée]rence|bon\s*de\s*commande|n[°ºo]\s*commande|\bcommande\b|\bref\b",
    re.IGNORECASE,
)
_KW_IMMAT_BL = re.compile(r"immatriculation|immat", re.IGNORECASE)
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Tolerant date: no word boundaries (OCR often glues the date to text/time, e.g.
# "le26/06/202616:47"); prefer a 4-digit year, else a 2-digit year.
_RE_DATE_LOOSE = re.compile(
    r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4}|\d{1,2}[./\-]\d{1,2}[./\-]\d{2})"
)
# Our own garage / the delivery company — never the supplier on a received BL.
_KW_OWN_PARTY = re.compile(r"garage\s*motors|al\s*delivery", re.IGNORECASE)
_KW_BL_TITLE = re.compile(r"bon\s*de\s*livraison", re.IGNORECASE)


def _guess_supplier_from_top(lines, top_n: int = 6) -> Optional[tuple[str, float]]:
    """Heuristic: the issuer (supplier) is the letterhead near the top.

    Skips our own garage / the delivery company, dates, the document title and
    mostly-numeric (address/phone/SIREN) lines. Confidence is lowered — it is a
    hint that the reviewer confirms (supplier HITL).
    """
    for line in lines[:top_n]:
        t = line.text.strip()
        if len(t) < 3:
            continue
        if _KW_OWN_PARTY.search(t) or _KW_BL_TITLE.search(t):
            continue
        if _RE_DATE_ANY.search(t):
            continue
        if sum(c.isdigit() for c in t) > len(t) / 2:
            continue
        if any(c.isalpha() for c in t):
            return t, round(line.confidence * 0.7, 4)
    return None


def extract_bon_de_livraison(result: RawOcrResult) -> FieldMap:
    """Extract structured fields from a supplier Bon de livraison.

    Header fields are reasonably reliable; line items are a best-effort,
    low-confidence hint (BL tables vary and OCR splits cells across lines).
    """
    fields: FieldMap = {}
    lines = result.lines

    # BL number — value near a "bon de livraison / n° / numéro" label, else a
    # code-with-digit on such a line.
    num = _value_near_keyword(lines, _KW_BL_NUMBER, _RE_BL_NUMBER)
    if not num:
        for line in lines:
            if _KW_BL_NUMBER.search(line.text) and not _KW_EXCLUDE_NUM.search(line.text):
                tok = _first_code_with_digit(line.text)
                if tok:
                    num = (tok, line.confidence)
                    break
    if num:
        fields["numero_bl"] = num

    # Delivery date — labelled, else the first date in the document. Uses the
    # tolerant pattern so a date glued to text/time still matches.
    d = _value_near_keyword(lines, _KW_DATE_BL, _RE_DATE_LOOSE)
    if not d:
        for line in lines:
            m = _RE_DATE_LOOSE.search(line.text)
            if m:
                d = (m.group(1), line.confidence)
                break
    if d:
        fields["date_bl"] = d

    # Order reference, if the BL prints the PO/commande number.
    ref = _value_near_keyword(lines, _KW_REF_COMMANDE, _RE_NUM_TOKEN)
    if ref:
        fields["reference_commande"] = ref

    # Vehicle plate (parts ordered for a specific repair). _RE_IMMATRICULATION
    # has two alternation groups, so read group(1) or group(2) explicitly.
    for line in lines:
        if not _KW_IMMAT_BL.search(line.text):
            continue
        m = _RE_IMMATRICULATION.search(line.text)
        if not m:
            after = _best_line_after_keyword(lines, _KW_IMMAT_BL)
            m = _RE_IMMATRICULATION.search(after[0]) if after else None
            conf = after[1] if after else line.confidence
        else:
            conf = line.confidence
        if m:
            val = (m.group(1) or m.group(2) or "").upper().replace(" ", "-")
            if val:
                fields["immatriculation"] = (val, conf)
        break

    # Supplier (issuer) — letterhead heuristic; confirmed via HITL on review.
    fournisseur = _guess_supplier_from_top(lines)
    if fournisseur:
        fields["fournisseur"] = fournisseur

    # Supplier email — first email on the document (associated to the supplier).
    for line in lines:
        m = _RE_EMAIL.search(line.text)
        if m:
            fields["email"] = (m.group(0), line.confidence)
            break

    # Totals (valued BLs). Anchor on the unique, bottom-most "TOTAL T.T.C." label
    # so HT/TVA/TTC are read from the same totals band — not the line-item column
    # headers ("Montant HT", …) higher up the page. The amount sits in the cell
    # below the label; the TVA amount excludes the "%T.V.A." rate column.
    ttc_kw = [ln for ln in lines if _KW_TOTAL_TTC.search(ln.text) and ln.box]
    band_y = (
        max(((ln.box[1] + ln.box[3]) / 2) for ln in ttc_kw) if ttc_kw else None
    )
    ht = _amount_near_keyword(lines, _KW_TOTAL_HT, band_y)
    if ht:
        fields["total_ht"] = ht
    tva = _amount_near_keyword(lines, _KW_TVA_AMOUNT, band_y)
    if tva:
        fields["tva"] = tva
    ttc = _amount_near_keyword(lines, _KW_TOTAL_TTC, band_y)
    if ttc:
        fields["total_ttc"] = ttc

    # Line items — best-effort JSON hint (low confidence).
    items = _extract_line_items(lines)
    if items:
        fields["lignes"] = items

    return fields


# ---------------------------------------------------------------------------
# On-demand single-field suggestion ("AI auto-match" from the recognised text)
# ---------------------------------------------------------------------------

# field_key → (label keyword | None, value regex | None). A None value regex
# means "take the line after the label" (free-text field).
_SUGGEST_SPECS: dict[str, tuple[Optional[re.Pattern], Optional[re.Pattern]]] = {
    # Invoices
    "date_facture": (_KW_DATE_FACTURE, _RE_DATE_ANY),
    "date_echeance": (_KW_DATE_ECHEANCE, _RE_DATE_ANY),
    "total_ht": (_KW_TOTAL_HT, _RE_AMOUNT_NO_PCT),
    "total_ttc": (_KW_TOTAL_TTC, _RE_AMOUNT_NO_PCT),
    "tva": (_KW_TVA_AMOUNT, _RE_AMOUNT_NO_PCT),
    "client": (_KW_CLIENT, None),
    "fournisseur": (_KW_FOURNISSEUR, None),
    # Bon de livraison
    "numero_bl": (_KW_BL_NUMBER, _RE_BL_NUMBER),
    "date_bl": (_KW_DATE_BL, _RE_DATE_LOOSE),
    "reference_commande": (_KW_REF_COMMANDE, _RE_NUM_TOKEN),
    "email": (None, _RE_EMAIL),
    # Carte grise
    "immatriculation": (None, _RE_IMMATRICULATION),
    "vin": (None, _RE_VIN),
    "proprietaire": (_KW_PROPRIETAIRE, None),
    "marque": (_KW_MARQUE, None),
    "modele": (_KW_MODELE, None),
    "date_mise_en_circulation": (_KW_DATE_MEC, _RE_DATE),
    # CIN
    "nom": (_KW_NOM, None),
    "prenom": (_KW_PRENOM, None),
    "cin": (None, _RE_CIN),
    "date_naissance": (_KW_DATE_NAISS, _RE_BIRTH_DATE),
}


def suggest_field(result: RawOcrResult, field_key: str) -> Optional[str]:
    """Best-guess value for a single field from the whole recognised text.

    Layout-aware: prefers the value near the field's label, then the first value
    matching the field's pattern, then a type-based fallback (any date / amount).
    """
    lines = result.lines

    if field_key == "numero_facture":
        numero = _extract_invoice_number(lines)
        return numero[0] if numero else None

    spec = _SUGGEST_SPECS.get(field_key)
    if spec:
        keyword, value_re = spec
        if value_re is not None:
            if keyword is not None:
                res = _value_near_keyword(lines, keyword, value_re)
                if res:
                    return res[0]
            for ln in lines:
                m = value_re.search(ln.text)
                if m:
                    return _match_value(m)
        elif keyword is not None:
            res = _best_line_after_keyword(lines, keyword)
            if res:
                return res[0]

    # Type-based fallback inferred from the field name.
    if "date" in field_key:
        for ln in lines:
            m = _RE_DATE_ANY.search(ln.text)
            if m:
                return _match_value(m)
    if any(t in field_key for t in ("total", "montant", "ht", "ttc", "tva")):
        for ln in lines:
            if _KW_AMOUNT_SKIP.search(ln.text):
                continue
            m = _RE_AMOUNT_NO_PCT.search(ln.text)
            if m:
                return _match_value(m)
    return None
