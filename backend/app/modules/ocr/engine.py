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


def _pdf_page_count(pdf_bytes: bytes) -> int:
    """Number of pages in a PDF (capped at MAX_PDF_PAGES), or 1 on failure."""
    try:
        import fitz  # type: ignore[import]  # PyMuPDF
    except ImportError:
        return 1
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return min(doc.page_count, MAX_PDF_PAGES) or 1


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
    """Abstract base class for OCR engines.

    Subclasses implement the synchronous, CPU-bound primitives
    (:meth:`_run_sync`, :meth:`ocr_region_sync`). The async wrappers here add
    optional idle-killed process isolation (see ``process_runner``) uniformly,
    so every engine benefits from it without duplicating the routing.
    """

    @abstractmethod
    def _run_sync(self, file_bytes: bytes) -> RawOcrResult:
        """Synchronous full-document OCR (CPU-bound)."""

    @abstractmethod
    def ocr_region_sync(self, file_bytes: bytes, box: tuple[int, int, int, int]) -> str:
        """Synchronous OCR of a rectangular region; returns the joined text."""

    # -- shared, engine-agnostic page rendering ----------------------------
    def page_count_sync(self, file_bytes: bytes) -> int:
        """Number of preview pages (PDFs capped at MAX_PDF_PAGES; images = 1)."""
        if _is_pdf(file_bytes):
            return max(1, _pdf_page_count(file_bytes))
        return 1

    def render_page_png_sync(self, file_bytes: bytes, page_index: int = 0) -> bytes:
        """Return the given page (0-based) as PNG bytes.

        PDFs are rasterised at PDF_RENDER_DPI (same space as the layout boxes so
        the highlight overlay aligns); images are re-encoded to PNG and ignore
        ``page_index``. On any failure the original bytes are returned unchanged.
        """
        import io as _io

        if _is_pdf(file_bytes):
            pages = _pdf_to_image_bytes(file_bytes)
            if not pages:
                return b""
            idx = max(0, min(page_index, len(pages) - 1))
            return pages[idx]
        try:
            from PIL import Image  # type: ignore[import]

            arr = _bytes_to_numpy(file_bytes)
            buf = _io.BytesIO()
            Image.fromarray(arr).save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return file_bytes

    def render_first_page_png_sync(self, file_bytes: bytes) -> bytes:
        """Return the document's first page as PNG bytes (see render_page_png_sync)."""
        return self.render_page_png_sync(file_bytes, 0)

    # -- async wrappers (optional idle-killed worker process) --------------
    async def run_ocr(self, file_bytes: bytes) -> RawOcrResult:
        """Run full-document OCR, optionally in an idle-killed worker process."""
        from app.modules.ocr.process_runner import get_runner

        loop = asyncio.get_running_loop()
        runner = get_runner()
        if runner is None:
            return await loop.run_in_executor(None, self._run_sync, file_bytes)
        return await loop.run_in_executor(
            None, runner.submit, _subprocess_run_ocr, file_bytes
        )

    async def run_ocr_region(self, file_bytes: bytes, box: tuple[int, int, int, int]) -> str:
        from app.modules.ocr.process_runner import get_runner

        loop = asyncio.get_running_loop()
        runner = get_runner()
        if runner is None:
            return await loop.run_in_executor(None, self.ocr_region_sync, file_bytes, box)
        return await loop.run_in_executor(
            None, runner.submit, _subprocess_ocr_region, file_bytes, box
        )

    async def render_first_page_png(self, file_bytes: bytes) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.render_first_page_png_sync, file_bytes)

    async def render_page_png(self, file_bytes: bytes, page_index: int = 0) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.render_page_png_sync, file_bytes, page_index
        )

    async def page_count(self, file_bytes: bytes) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.page_count_sync, file_bytes)


# Module-level entry points executed inside the OCR worker process. They must be
# importable (picklable) and resolve the *configured* engine, so isolation works
# for whichever engine is active. They call the synchronous methods directly so
# they never re-enter the async routing above.
def _subprocess_run_ocr(file_bytes: bytes) -> RawOcrResult:
    return get_ocr_engine()._run_sync(file_bytes)


def _subprocess_ocr_region(file_bytes: bytes, box: tuple[int, int, int, int]) -> str:
    return get_ocr_engine().ocr_region_sync(file_bytes, box)


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

                logger.info(
                    "PaddleOCR: initialising (lang=%s, version=%s, doc_ori=%s, "
                    "unwarp=%s, textline_ori=%s)",
                    lang,
                    version,
                    cfg.cfg_ocr_use_doc_orientation,
                    cfg.cfg_ocr_use_doc_unwarping,
                    cfg.cfg_ocr_use_textline_orientation,
                )
                self._paddle = PaddleOCR(
                    lang=lang,
                    ocr_version=version,
                    # Skip the auxiliary preprocessing models unless a deployment
                    # explicitly needs them — they cost RAM, image size and
                    # latency without helping on flat garage documents.
                    use_doc_orientation_classify=cfg.cfg_ocr_use_doc_orientation,
                    use_doc_unwarping=cfg.cfg_ocr_use_doc_unwarping,
                    use_textline_orientation=cfg.cfg_ocr_use_textline_orientation,
                )
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


class OnnxOcrEngine(OcrEngine):
    """ONNX Runtime engine (RapidOCR / PP-OCR) — no ``paddlepaddle`` dependency.

    Roughly half the peak RAM and a small fraction of the disk of the Paddle
    engine (measured ~233 MB peak vs ~525 MB; ~52 MB of wheels vs ~780 MB).
    Selected via ``cfg_ocr_engine='onnx'``.

    NOTE: RapidOCR's default recognition model is PP-OCRv4 (ch/en). For French
    accents (é, è, à, ç) point it at the latin PP-OCRv3 ONNX model via
    ``cfg_ocr_onnx_rec_model_path`` / ``cfg_ocr_onnx_rec_keys_path`` and validate
    on real documents before making this the default engine.
    """

    _instance: Optional["OnnxOcrEngine"] = None
    _engine = None  # lazy RapidOCR

    @classmethod
    def get(cls) -> "OnnxOcrEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_engine(self):
        if self._engine is None:
            import os

            from app.core.config import get_settings

            cfg = get_settings()
            # Default to the vendored latin PP-OCRv3 recognition model so French
            # accents (é, è, ô, ç…) decode correctly out of the box. RapidOCR's
            # own bundled model is Chinese/English and mangles accents. A
            # deployment can still override both paths via config.
            models_dir = os.path.join(os.path.dirname(__file__), "models")
            default_rec = os.path.join(models_dir, "latin_PP-OCRv3_rec.onnx")
            default_keys = os.path.join(models_dir, "latin_dict.txt")
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore[import]

                kwargs: dict = {}
                rec_path = getattr(cfg, "cfg_ocr_onnx_rec_model_path", "") or (
                    default_rec if os.path.exists(default_rec) else ""
                )
                rec_keys = getattr(cfg, "cfg_ocr_onnx_rec_keys_path", "") or (
                    default_keys if os.path.exists(default_keys) else ""
                )
                if rec_path:
                    kwargs["rec_model_path"] = rec_path
                if rec_keys:
                    kwargs["rec_keys_path"] = rec_keys
                logger.info(
                    "OnnxOcrEngine: initialising RapidOCR (rec_model=%s)",
                    rec_path or "default(PP-OCRv4 ch/en)",
                )
                self._engine = RapidOCR(**kwargs)
                logger.info("OnnxOcrEngine: initialised successfully")
            except Exception as exc:
                logger.warning(
                    "ONNX OCR unavailable — OCR will return empty results. Cause: %s: %s",
                    type(exc).__name__,
                    exc,
                )
                self._engine = _NullOnnx()
        return self._engine

    def _ocr_array(self, img_array) -> list[OcrLine]:
        """Run RapidOCR on a numpy image array → list of OcrLine."""
        engine = self._get_engine()
        try:
            result, _elapsed = engine(img_array)
        except Exception:
            # Full traceback so a real failure (e.g. model/shape mismatch) is
            # diagnosable instead of surfacing as a silent empty extraction.
            logger.exception("ONNX OCR execution error")
            return []
        lines: list[OcrLine] = []
        for item in result or []:
            try:
                box_pts, text, score = item[0], item[1], item[2]
            except (IndexError, TypeError):
                continue
            lines.append(
                OcrLine(text=str(text), confidence=float(score), box=_poly_to_box(box_pts))
            )
        return lines

    def _run_sync(self, file_bytes: bytes) -> RawOcrResult:
        width, height = 0, 0
        lines: list[OcrLine] = []
        if _is_pdf(file_bytes):
            for page_idx, page_bytes in enumerate(_pdf_to_image_bytes(file_bytes)):
                arr = _bytes_to_numpy(page_bytes)
                if page_idx == 0:
                    height, width = arr.shape[:2]
                lines.extend(self._ocr_array(arr))
        else:
            arr = _bytes_to_numpy(file_bytes)
            height, width = arr.shape[:2]
            lines = self._ocr_array(arr)

        logger.info("OnnxOcrEngine: extracted %d line(s)", len(lines))
        full_text = "\n".join(line.text for line in lines)
        return RawOcrResult(lines=lines, full_text=full_text, width=width, height=height)

    def ocr_region_sync(self, file_bytes: bytes, box: tuple[int, int, int, int]) -> str:
        if _is_pdf(file_bytes):
            pages = _pdf_to_image_bytes(file_bytes)
            if not pages:
                return ""
            base = _bytes_to_numpy(pages[0])
        else:
            base = _bytes_to_numpy(file_bytes)

        h, w = base.shape[:2]
        pad = 3
        x1, y1, x2, y2 = (int(box[0]) - pad, int(box[1]) - pad, int(box[2]) + pad, int(box[3]) + pad)
        x1, x2 = max(0, min(x1, w)), max(0, min(x2, w))
        y1, y2 = max(0, min(y1, h)), max(0, min(y2, h))
        if x2 - x1 < 3 or y2 - y1 < 3:
            return ""
        crop = base[y1:y2, x1:x2]
        return " ".join(ln.text for ln in self._ocr_array(crop)).strip()


class _NullOnnx:
    """Fallback used when rapidocr-onnxruntime is not installed."""

    def __call__(self, _img, **_kwargs):
        return [], None


def get_ocr_engine() -> OcrEngine:
    """Return the configured OCR engine singleton.

    ``cfg_ocr_engine='paddle'`` (default) or ``'onnx'``. Unknown values fall back
    to Paddle so a typo can never silently disable OCR.
    """
    from app.core.config import get_settings

    name = (getattr(get_settings(), "cfg_ocr_engine", "paddle") or "paddle").lower()
    if name == "onnx":
        return OnnxOcrEngine.get()
    return PaddleOcrEngine.get()
