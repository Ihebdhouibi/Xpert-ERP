"""OCR engine abstraction — ABC + PaddleOCR implementation.

PaddleOCR is CPU-bound. All calls to PaddleOCR are run in a thread executor
so the event loop is not blocked.

PaddleOCR (and its C++ backend) writes directly to OS file descriptors 1/2,
bypassing Python's sys.stdout/sys.stderr.  We suppress those at the OS level
(dup2 to /dev/null) during init and inference so the terminal stays clean.
Meaningful diagnostics are emitted via the Python logger instead.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

ENGINE_VERSION = "paddleocr-3"


@contextmanager
def _suppress_c_stdio():
    """Redirect OS-level file descriptors 1 (stdout) and 2 (stderr) to /dev/null.

    PaddleOCR's C++ backend writes directly to the raw fds, not through
    Python's sys.stdout/sys.stderr, so only an fd-level redirect works.
    The context manager restores the original fds on exit.
    """
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved_stdout = os.dup(1)
    saved_stderr = os.dup(2)
    try:
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(saved_stdout, 1)
        os.dup2(saved_stderr, 2)
        os.close(saved_stdout)
        os.close(saved_stderr)
        os.close(devnull_fd)


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
                with _suppress_c_stdio():
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
            with _suppress_c_stdio():
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
