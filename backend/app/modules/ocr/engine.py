"""OCR engine abstraction — ABC + PaddleOCR implementation.

PaddleOCR is CPU-bound. All calls to PaddleOCR are run in a thread executor
so the event loop is not blocked.
"""
from __future__ import annotations

import asyncio
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

ENGINE_VERSION = "paddleocr-3"


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

                # PaddleOCR 3.x — use_angle_cls / show_log / use_gpu are removed.
                # "fr" is only available in PP-OCRv3; PP-OCRv5 (default) only
                # supports ch/en/japan/chinese_cht.
                self._paddle = PaddleOCR(lang="fr", ocr_version="PP-OCRv3")
                logger.info("PaddleOCR initialised (lang=fr)")
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
            # PaddleOCR 3.x: predict() returns a list of OCRResult objects
            results = paddle.predict(image_bytes)
        except Exception as exc:
            logger.error("PaddleOCR execution error: %s", exc)
            return RawOcrResult(lines=[], full_text="")

        lines: list[OcrLine] = []
        for res in results:
            # Each OCRResult is dict-like: res["rec_texts"], res["rec_scores"]
            try:
                texts = res["rec_texts"]
                scores = res["rec_scores"]
                for text, conf in zip(texts, scores):
                    lines.append(OcrLine(text=str(text), confidence=float(conf)))
            except (KeyError, TypeError, ValueError):
                continue

        full_text = "\n".join(line.text for line in lines)
        return RawOcrResult(lines=lines, full_text=full_text)


class _NullPaddle:
    """Fallback used when paddleocr is not installed (test / CI environments)."""

    def predict(self, _input, **_kwargs):
        return []
