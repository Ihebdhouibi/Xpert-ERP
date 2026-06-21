"""The OCR worker process must capture engine errors to a log file.

OCR runs in a spawned subprocess that never runs the app's configure_logging, so
without dedicated setup the engine's failure logs vanish and an OCR failure looks
like a silent empty result. This guards that the worker logging initializer
writes engine records to logs/ocr-worker.log.
"""
from __future__ import annotations

import logging


def test_worker_logging_captures_engine_errors(tmp_path, monkeypatch):
    from app.core import config
    from app.modules.ocr.process_runner import _init_worker_logging

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "log_dir", str(tmp_path), raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)

    root = logging.getLogger()
    preexisting = list(root.handlers)
    try:
        _init_worker_logging()
        # Engine uses logging.getLogger(__name__); it propagates to root.
        logging.getLogger("app.modules.ocr.engine").error("ONNX OCR execution error MARKER")
        for h in root.handlers:
            h.flush()

        log_file = tmp_path / "ocr-worker.log"
        assert log_file.exists(), "worker did not create ocr-worker.log"
        contents = log_file.read_text(encoding="utf-8")
        assert "ONNX OCR execution error MARKER" in contents
        assert "ocr-worker" in contents  # the worker formatter tag
    finally:
        for h in list(root.handlers):
            if h not in preexisting:
                root.removeHandler(h)
                h.close()


def test_worker_logging_is_idempotent(tmp_path, monkeypatch):
    from app.core import config
    from app.modules.ocr.process_runner import _init_worker_logging

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "log_dir", str(tmp_path), raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)

    root = logging.getLogger()
    preexisting = list(root.handlers)
    try:
        _init_worker_logging()
        _init_worker_logging()  # second call must not double-attach
        added = [h for h in root.handlers if getattr(h, "_ocr_worker", False)]
        # one rotating file handler + one stream handler, not four
        assert len(added) == 2
    finally:
        for h in list(root.handlers):
            if h not in preexisting:
                root.removeHandler(h)
                h.close()
