"""Tests for the ONNX (RapidOCR) engine and engine factory (cost-opt Opt 4)."""
from __future__ import annotations

import io

import numpy as np
import pytest

from app.modules.ocr.engine import (
    OnnxOcrEngine,
    PaddleOcrEngine,
    RawOcrResult,
    get_ocr_engine,
)


# ---- factory selection ------------------------------------------------------

def test_factory_defaults_to_paddle(monkeypatch):
    from app.core import config

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "cfg_ocr_engine", "paddle", raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)
    assert isinstance(get_ocr_engine(), PaddleOcrEngine)


def test_factory_selects_onnx(monkeypatch):
    from app.core import config

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "cfg_ocr_engine", "onnx", raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)
    assert isinstance(get_ocr_engine(), OnnxOcrEngine)


def test_factory_unknown_value_falls_back_to_paddle(monkeypatch):
    from app.core import config

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "cfg_ocr_engine", "banana", raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)
    assert isinstance(get_ocr_engine(), PaddleOcrEngine)


# ---- RapidOCR output mapping (no model; fake engine) ------------------------

def test_onnx_maps_rapidocr_output_to_lines(monkeypatch):
    """RapidOCR returns [[box, text, score], ...]; map to OcrLine with boxes."""
    engine = OnnxOcrEngine()

    class FakeRapid:
        def __call__(self, _img, **_k):
            boxes = [[10, 10], [110, 10], [110, 40], [10, 40]]
            return ([[boxes, "AB-123-CD", 0.97], [boxes, "DUPONT", 0.88]], 0.1)

    engine._engine = FakeRapid()
    img = np.zeros((50, 200, 3), dtype=np.uint8)
    lines = engine._ocr_array(img)
    assert [ln.text for ln in lines] == ["AB-123-CD", "DUPONT"]
    assert lines[0].confidence == pytest.approx(0.97)
    assert lines[0].box == [10, 10, 110, 40]  # normalised [x1,y1,x2,y2]


def test_onnx_run_sync_builds_rawresult(monkeypatch):
    engine = OnnxOcrEngine()

    class FakeRapid:
        def __call__(self, _img, **_k):
            return ([[[[0, 0], [50, 0], [50, 20], [0, 20]], "HELLO", 0.9]], 0.1)

    engine._engine = FakeRapid()
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 80), "white").save(buf, format="PNG")
    result = engine._run_sync(buf.getvalue())
    assert isinstance(result, RawOcrResult)
    assert result.full_text == "HELLO"
    assert result.width == 200 and result.height == 80


def test_onnx_engine_degrades_gracefully_without_library(monkeypatch):
    """A missing rapidocr install yields empty results, not a crash."""
    import sys

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    engine = OnnxOcrEngine()
    engine._engine = None
    img = np.zeros((40, 120, 3), dtype=np.uint8)
    assert engine._ocr_array(img) == []


# ---- real end-to-end parity on a synthetic document -------------------------

def test_onnx_extracts_text_end_to_end():
    """Smoke parity: the real ONNX engine reads plain text off a rendered image."""
    pytest.importorskip("rapidocr_onnxruntime")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 60), "IMMATRICULATION AB-123-CD", fill="black")
    draw.text((40, 140), "VIN WVWZZZ1JZXW000001", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = OnnxOcrEngine()._run_sync(buf.getvalue())

    text = result.full_text.upper().replace(" ", "")
    assert "AB-123-CD".replace("-", "") in text.replace("-", "")
    assert "WVWZZZ1JZXW000001" in text
