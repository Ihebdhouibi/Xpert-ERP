"""OCR engine abstraction — ABC + PaddleOCR implementation.

PaddleOCR is CPU-bound. All calls to PaddleOCR are run in a thread executor
so the event loop is not blocked.

During the one-time model initialisation PaddleOCR emits model-loading messages
via Python print() calls and C++ writes to raw file descriptors 1/2.
`_redirect_paddle_output()` captures all of these and appends them to system.log.
"""
from __future__ import annotations

import asyncio
import io
import logging
import logging.handlers
import os
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

ENGINE_VERSION = "paddleocr-3"


@contextmanager
def _redirect_paddle_output():
    """Capture PaddleOCR init output (Python print + C-level fds) → system.log.

    Strategy:
    - Replace sys.stdout / sys.stderr so Python print() calls go to the log file.
    - os.dup2 fd 1 and fd 2 so C++ glog writes also go to the log file.
    - Python logging handlers are NOT affected: StreamHandler stores the original
      terminal stderr object at creation time, not via sys.stderr lookup.
    - On any OS error (e.g. unavailable log path) we fall through silently.
    """
    # Locate system.log from the running logger configuration
    log_path: str | None = None
    for _h in logging.getLogger("system").handlers:
        if isinstance(_h, logging.handlers.RotatingFileHandler):
            log_path = _h.baseFilename
            break

    if log_path is None:
        yield
        return

    # Flush Python buffers before touching fds
    try:
        sys.stdout.flush()
    except Exception:
        pass
    try:
        sys.stderr.flush()
    except Exception:
        pass

    try:
        _log_fh = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        yield
        return

    _saved_fd1 = os.dup(1)
    _saved_fd2 = os.dup(2)
    _saved_stdout = sys.stdout
    _saved_stderr = sys.stderr
    try:
        # Redirect C-level fds first
        os.dup2(_log_fh.fileno(), 1)
        os.dup2(_log_fh.fileno(), 2)
        # Redirect Python-level streams (captures print() and warnings.warn())
        sys.stdout = _log_fh
        sys.stderr = _log_fh
        yield
    finally:
        try:
            _log_fh.flush()
        except Exception:
            pass
        # Restore Python streams before restoring fds
        sys.stdout = _saved_stdout
        sys.stderr = _saved_stderr
        os.dup2(_saved_fd1, 1)
        os.dup2(_saved_fd2, 2)
        os.close(_saved_fd1)
        os.close(_saved_fd2)
        try:
            _log_fh.close()
        except Exception:
            pass


def _bytes_to_numpy(image_bytes: bytes):
    """Convert raw image bytes to a numpy uint8 array (H, W, 3) for PaddleOCR."""
    try:
        from PIL import Image  # type: ignore[import]
        import numpy as np

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(img)
    except Exception as exc:
        raise ValueError(f"Cannot decode image bytes: {exc}") from exc


@dataclass
class OcrLine:
    """One recognised text block with its confidence."""

    text: str
    confidence: float


@dataclass
class RawOcrResult:
    """Raw output from an OCR engine run."""

    lines: list[OcrLine]
    full_text: str


class OcrEngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def _run_sync(self, image_bytes: bytes) -> RawOcrResult:
        """Synchronous OCR execution (CPU-bound)."""

    async def run_ocr(self, image_bytes: bytes) -> RawOcrResult:
        """Run OCR in a thread executor to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_sync, image_bytes)


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR 3.x engine — lazy-loaded singleton per process."""

    _instance: Optional["PaddleOcrEngine"] = None
    _paddle = None  # lazy

    @classmethod
    def get(cls) -> "PaddleOcrEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_paddle(self):
        if self._paddle is None:
            try:
                from paddleocr import PaddleOCR  # type: ignore[import]

                logger.info("PaddleOCR: initialising (lang=fr, version=PP-OCRv3)")
                with _redirect_paddle_output():
                    self._paddle = PaddleOCR(lang="fr", ocr_version="PP-OCRv3")
                logger.info("PaddleOCR: initialised successfully")
            except ImportError:
                logger.warning(
                    "paddleocr not installed — OCR will return empty results. "
                    "Install it: pip install paddleocr paddlepaddle"
                )
                self._paddle = _NullPaddle()
        return self._paddle

    def _run_sync(self, image_bytes: bytes) -> RawOcrResult:
        paddle = self._get_paddle()
        try:
            img_array = _bytes_to_numpy(image_bytes)
            logger.debug("PaddleOCR: running predict on image shape=%s", img_array.shape)
            results = paddle.predict(img_array)
        except Exception as exc:
            logger.error("PaddleOCR execution error: %s", exc)
            return RawOcrResult(lines=[], full_text="")

        lines: list[OcrLine] = []
        logger.debug("PaddleOCR: predict returned %d result block(s)", len(results) if results else 0)
        for block_idx, res in enumerate(results):
            try:
                texts = res["rec_texts"]
                scores = res["rec_scores"]
                logger.debug(
                    "PaddleOCR: block %d has %d text line(s)", block_idx, len(texts)
                )
                for text, conf in zip(texts, scores):
                    lines.append(OcrLine(text=str(text), confidence=float(conf)))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("PaddleOCR: could not parse result block %d: %s", block_idx, exc)
                continue

        logger.info("PaddleOCR: extracted %d line(s) from image", len(lines))
        full_text = "\n".join(line.text for line in lines)
        return RawOcrResult(lines=lines, full_text=full_text)


class _NullPaddle:
    """Fallback used when paddleocr is not installed (test / CI environments)."""

    def predict(self, _input, **_kwargs):
        return []
