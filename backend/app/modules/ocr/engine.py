"""OCR engine abstraction — ABC + PaddleOCR implementation.

PaddleOCR is CPU-bound. All calls to PaddleOCR are run in a thread executor
so the event loop is not blocked.

PaddleOCR prints model-loading messages to stdout during first initialisation
(lazy, one-time only). These are expected in a dev environment and are harmless.
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

# Max PDF pages to OCR (guards against huge multi-page documents).
MAX_PDF_PAGES = 5
# Render resolution for PDF pages — higher DPI = better OCR on small text.
PDF_RENDER_DPI = 200


def _is_pdf(data: bytes) -> bool:
    """Detect a PDF by its magic header."""
    return data[:5] == b"%PDF-"


def _bytes_to_numpy(image_bytes: bytes):
    """Convert raw image bytes to a numpy uint8 array (H, W, 3) for PaddleOCR."""
    try:
        from PIL import Image  # type: ignore[import]
        import numpy as np

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(img)
    except Exception as exc:
        raise ValueError(f"Cannot decode image bytes: {exc}") from exc


def _pdf_to_image_bytes(pdf_bytes: bytes) -> list[bytes]:
    """Render the first ``MAX_PDF_PAGES`` pages of a PDF to PNG bytes.

    Uses PyMuPDF (fitz) which ships self-contained wheels (no system poppler).
    """
    try:
        import fitz  # type: ignore[import]  # PyMuPDF
    except ImportError:
        logger.warning("pymupdf not installed — cannot OCR PDF documents")
        return []

    images: list[bytes] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page_count = doc.page_count
        for page_index in range(min(page_count, MAX_PDF_PAGES)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
            images.append(pix.tobytes("png"))
        if page_count > MAX_PDF_PAGES:
            logger.info(
                "pdf_truncated_for_ocr page_count=%d max=%d", page_count, MAX_PDF_PAGES
            )
    return images


@dataclass
class OcrLine:
    """One recognised text block with its confidence and bounding box.

    ``box`` is ``[x1, y1, x2, y2]`` in the source image's pixel coordinates
    (or ``None`` when unavailable). Used to highlight the line in the preview.
    """

    text: str
    confidence: float
    box: Optional[list[int]] = None


@dataclass
class RawOcrResult:
    """Raw output from an OCR engine run."""

    lines: list[OcrLine]
    full_text: str
    # Source image dimensions (first page for PDFs) for scaling highlight boxes.
    width: int = 0
    height: int = 0


def _poly_to_box(raw_box) -> Optional[list[int]]:
    """Normalise a PaddleOCR box/polygon to ``[x1, y1, x2, y2]`` ints."""
    try:
        import numpy as np

        arr = np.array(raw_box).reshape(-1)
        if arr.size == 4:
            x1, y1, x2, y2 = arr
            return [int(x1), int(y1), int(x2), int(y2)]
        pts = np.array(raw_box).reshape(-1, 2)
        return [
            int(pts[:, 0].min()),
            int(pts[:, 1].min()),
            int(pts[:, 0].max()),
            int(pts[:, 1].max()),
        ]
    except Exception:
        return None


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
            from app.core.config import get_settings

            cfg = get_settings()
            lang = cfg.cfg_ocr_lang
            version = cfg.cfg_ocr_engine_version
            try:
                from paddleocr import PaddleOCR  # type: ignore[import]

                logger.info("PaddleOCR: initialising (lang=%s, version=%s)", lang, version)
                self._paddle = PaddleOCR(lang=lang, ocr_version=version)
                logger.info("PaddleOCR: initialised successfully")
            except Exception as exc:  # ImportError, missing native libs, model download, etc.
                logger.warning(
                    "PaddleOCR unavailable — OCR will return empty results. "
                    "Cause: %s: %s",
                    type(exc).__name__,
                    exc,
                )
                self._paddle = _NullPaddle()
        return self._paddle

    def _ocr_image(self, image_bytes: bytes) -> tuple[list[OcrLine], tuple[int, int]]:
        """Run PaddleOCR on a single image; return (lines, (width, height))."""
        paddle = self._get_paddle()
        try:
            img_array = _bytes_to_numpy(image_bytes)
            height, width = img_array.shape[:2]
            logger.debug("PaddleOCR: running predict on image shape=%s", img_array.shape)
            results = paddle.predict(img_array)
        except Exception as exc:
            logger.error("PaddleOCR execution error: %s", exc)
            return [], (0, 0)

        lines: list[OcrLine] = []
        logger.debug("PaddleOCR: predict returned %d result block(s)", len(results) if results else 0)
        for block_idx, res in enumerate(results):
            try:
                texts = res["rec_texts"]
                scores = res["rec_scores"]
                boxes = res.get("rec_boxes")
                if boxes is None or len(boxes) == 0:
                    boxes = res.get("rec_polys")
                logger.debug(
                    "PaddleOCR: block %d has %d text line(s)", block_idx, len(texts)
                )
                for i, (text, conf) in enumerate(zip(texts, scores)):
                    box = None
                    if boxes is not None and i < len(boxes):
                        box = _poly_to_box(boxes[i])
                    lines.append(OcrLine(text=str(text), confidence=float(conf), box=box))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("PaddleOCR: could not parse result block %d: %s", block_idx, exc)
                continue
        return lines, (width, height)

    def ocr_region_sync(self, file_bytes: bytes, box: tuple[int, int, int, int]) -> str:
        """OCR just a rectangular region [x1,y1,x2,y2] of the document image.

        Coordinates are in the same pixel space as the stored layout boxes
        (original image, or first page rendered at PDF_RENDER_DPI for PDFs).
        """
        import io as _io

        try:
            from PIL import Image  # type: ignore[import]
        except Exception:
            return ""

        if _is_pdf(file_bytes):
            pages = _pdf_to_image_bytes(file_bytes)
            if not pages:
                return ""
            base = _bytes_to_numpy(pages[0])
        else:
            base = _bytes_to_numpy(file_bytes)

        h, w = base.shape[:2]
        pad = 3  # small margin so glyphs at the edges aren't clipped
        x1, y1, x2, y2 = (int(box[0]) - pad, int(box[1]) - pad, int(box[2]) + pad, int(box[3]) + pad)
        x1, x2 = max(0, min(x1, w)), max(0, min(x2, w))
        y1, y2 = max(0, min(y1, h)), max(0, min(y2, h))
        if x2 - x1 < 3 or y2 - y1 < 3:
            return ""
        crop = base[y1:y2, x1:x2]
        buf = _io.BytesIO()
        Image.fromarray(crop).save(buf, format="PNG")
        lines = self._ocr_image(buf.getvalue())[0]
        return " ".join(ln.text for ln in lines).strip()

    async def run_ocr_region(self, file_bytes: bytes, box: tuple[int, int, int, int]) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.ocr_region_sync, file_bytes, box)

    def render_first_page_png_sync(self, file_bytes: bytes) -> bytes:
        """Return the document's first page as PNG bytes.

        PDFs are rasterised at PDF_RENDER_DPI (same space as the layout boxes so
        the highlight overlay aligns); images are re-encoded to PNG. On any
        failure the original bytes are returned unchanged.
        """
        import io as _io

        if _is_pdf(file_bytes):
            pages = _pdf_to_image_bytes(file_bytes)
            return pages[0] if pages else b""
        try:
            from PIL import Image  # type: ignore[import]

            arr = _bytes_to_numpy(file_bytes)
            buf = _io.BytesIO()
            Image.fromarray(arr).save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return file_bytes

    async def render_first_page_png(self, file_bytes: bytes) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.render_first_page_png_sync, file_bytes)

    def _run_sync(self, file_bytes: bytes) -> RawOcrResult:
        # PDFs are rasterised page-by-page; images are OCR'd directly.
        width, height = 0, 0
        if _is_pdf(file_bytes):
            page_images = _pdf_to_image_bytes(file_bytes)
            lines: list[OcrLine] = []
            for page_idx, page_bytes in enumerate(page_images):
                page_lines, page_dims = self._ocr_image(page_bytes)
                if page_idx == 0:
                    width, height = page_dims  # highlight overlay only applies to page 1
                logger.debug("PaddleOCR: page %d -> %d line(s)", page_idx + 1, len(page_lines))
                lines.extend(page_lines)
        else:
            lines, (width, height) = self._ocr_image(file_bytes)

        logger.info("PaddleOCR: extracted %d line(s)", len(lines))
        full_text = "\n".join(line.text for line in lines)
        return RawOcrResult(lines=lines, full_text=full_text, width=width, height=height)


class _NullPaddle:
    """Fallback used when paddleocr is not installed (test / CI environments)."""

    def predict(self, _input, **_kwargs):
        return []
