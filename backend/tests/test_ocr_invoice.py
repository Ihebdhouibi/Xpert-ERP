"""Unit tests for invoice OCR extractors and PDF engine routing."""
from __future__ import annotations

from unittest.mock import patch

from app.modules.ocr import extractors
from app.modules.ocr.engine import OcrLine, PaddleOcrEngine, RawOcrResult


def _result(*texts_conf: tuple[str, float]) -> RawOcrResult:
    lines = [OcrLine(text=t, confidence=c) for t, c in texts_conf]
    return RawOcrResult(lines=lines, full_text="\n".join(t for t, _ in texts_conf))


# ---------------------------------------------------------------------------
# Engine: PDFs are rasterised page-by-page then OCR'd
# ---------------------------------------------------------------------------

class TestPdfEngine:
    def test_pdf_routed_through_rasteriser(self) -> None:
        engine = PaddleOcrEngine()
        pages = [b"page-1-png", b"page-2-png"]

        def fake_ocr_image(image_bytes: bytes):
            idx = pages.index(image_bytes) + 1
            return [OcrLine(text=f"page{idx}", confidence=0.9)], (600, 800)

        with patch(
            "app.modules.ocr.engine._pdf_to_image_bytes", return_value=pages
        ):
            engine._ocr_image = fake_ocr_image  # type: ignore[assignment]
            result = engine._run_sync(b"%PDF-1.7 fake")

        assert [ln.text for ln in result.lines] == ["page1", "page2"]
        assert result.full_text == "page1\npage2"
        assert (result.width, result.height) == (600, 800)

    def test_non_pdf_uses_image_path(self) -> None:
        engine = PaddleOcrEngine()
        engine._ocr_image = lambda b: ([OcrLine(text="img", confidence=0.8)], (100, 50))  # type: ignore[assignment]
        result = engine._run_sync(b"\xff\xd8\xff\xe0 jpeg")
        assert [ln.text for ln in result.lines] == ["img"]
        assert (result.width, result.height) == (100, 50)


# ---------------------------------------------------------------------------
# Extractors: supplier & customer invoices
# ---------------------------------------------------------------------------

class TestInvoiceExtractors:
    def test_extract_supplier_invoice_header(self) -> None:
        result = _result(
            ("Facture N° INV-2024-077", 0.95),
            ("Date facture 12/03/2024", 0.90),
            ("Echeance 12/04/2024", 0.88),
            ("Fournisseur", 0.92),
            ("PIECES AUTO SARL", 0.91),
            ("Total HT 1 250,00", 0.93),
            ("TVA 250,00", 0.93),
            ("Total TTC 1 500,00", 0.94),
        )
        fields = extractors.extract_supplier_invoice(result)

        assert fields["numero_facture"][0] == "INV-2024-077"
        assert fields["date_facture"][0] == "12/03/2024"
        assert fields["date_echeance"][0] == "12/04/2024"
        assert fields["fournisseur"][0] == "PIECES AUTO SARL"
        assert fields["total_ht"][0] == "1250.00"
        assert fields["total_ttc"][0] == "1500.00"

    def test_extract_invoice_uses_client_party(self) -> None:
        result = _result(
            ("FACTURE 2024/12", 0.95),
            ("Client", 0.9),
            ("Garage Dupont", 0.9),
            ("Net à payer 600,00", 0.9),
        )
        fields = extractors.extract_invoice(result)
        assert fields["client"][0] == "Garage Dupont"
        assert fields["total_ttc"][0] == "600.00"

    def test_line_items_low_confidence_json(self) -> None:
        result = _result(
            ("Plaquettes de frein 2 150,00 300,00", 0.9),
            ("Filtre a huile 1 45,00 45,00", 0.9),
        )
        fields = extractors.extract_invoice(result)
        assert "lignes" in fields
        # Line items are deliberately low-confidence (flagged for review)
        assert fields["lignes"][1] < 0.75
        assert "Plaquettes" in fields["lignes"][0]
