"""Tests for OCR engine lightweight-model configuration (cost-optimization Opt 2).

The engine must forward the auxiliary-model toggles to PaddleOCR, and the
defaults must be lean (all three auxiliary models off) so a stock deployment
gets the smaller RAM / image footprint without extra configuration.
"""
from __future__ import annotations

import sys
import types

from app.core.config import get_settings


def test_defaults_are_lean():
    cfg = get_settings()
    assert cfg.cfg_ocr_use_doc_orientation is False
    assert cfg.cfg_ocr_use_doc_unwarping is False
    assert cfg.cfg_ocr_use_textline_orientation is False


def test_engine_forwards_auxiliary_flags(monkeypatch):
    """_get_paddle() must pass the config toggles to the PaddleOCR constructor."""
    captured: dict = {}

    class FakePaddle:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def predict(self, *_a, **_k):
            return []

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddle))

    # Import after patching so the in-function import resolves to the fake.
    from app.modules.ocr.engine import PaddleOcrEngine

    engine = PaddleOcrEngine()
    engine._paddle = None  # ensure a fresh load on this instance
    engine._get_paddle()

    assert captured["use_doc_orientation_classify"] is False
    assert captured["use_doc_unwarping"] is False
    assert captured["use_textline_orientation"] is False
    assert captured["ocr_version"] == "PP-OCRv3"
    assert captured["lang"] == "fr"


def test_engine_honours_enabled_flags(monkeypatch):
    """When a deployment re-enables the auxiliary models, they propagate."""
    captured: dict = {}

    class FakePaddle:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def predict(self, *_a, **_k):
            return []

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddle))

    from app.core import config as config_module
    from app.modules.ocr.engine import PaddleOcrEngine

    cfg = get_settings()
    monkeypatch.setattr(cfg, "cfg_ocr_use_textline_orientation", True, raising=False)
    monkeypatch.setattr(config_module, "get_settings", lambda: cfg)
    # engine imports get_settings lazily inside _get_paddle from app.core.config
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)

    engine = PaddleOcrEngine()
    engine._paddle = None
    engine._get_paddle()

    assert captured["use_textline_orientation"] is True
