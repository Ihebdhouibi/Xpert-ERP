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
