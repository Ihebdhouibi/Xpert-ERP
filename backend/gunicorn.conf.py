"""Gunicorn configuration for the Xpert ERP backend.

Why this file exists
--------------------
OCR (PaddleOCR) runs as a FastAPI ``BackgroundTask`` *inside the web worker
process*. Every gunicorn worker that handles a scan lazily loads its own copy of
the OCR model (~0.6 GB resident, ~0.6 GB peak each). With N workers that becomes
N × 0.6 GB of duplicated model memory — the single biggest driver of the VM RAM
size.

For a single-garage deployment one worker is the right default: it caps the OCR
model to **exactly one instance** and is plenty for the expected concurrency
(async I/O is still handled concurrently within that worker; CPU-bound OCR runs
in a thread and PaddlePaddle releases the GIL during inference).

The worker count stays env-configurable so the same image scales up later
without a rebuild:

    GUNICORN_WORKERS=2   # or WEB_CONCURRENCY=2 (gunicorn's conventional name)
"""
from __future__ import annotations

import os


def _resolve_workers() -> int:
    """Resolve the worker count from env, defaulting to 1 (single-garage).

    Precedence: ``GUNICORN_WORKERS`` > ``WEB_CONCURRENCY`` > 1. Any invalid or
    non-positive value falls back to 1 so a bad env var can never take the API
    down or silently spawn a model-per-worker fleet.
    """
    raw = os.getenv("GUNICORN_WORKERS") or os.getenv("WEB_CONCURRENCY") or "1"
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return value if value > 0 else 1


bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = _resolve_workers()

# OCR of a multi-page PDF can run for a while as a background task; give the
# worker a generous timeout so it is not killed mid-scan, and allow a clean
# graceful shutdown window.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Recycle workers periodically to bound any long-run memory growth from the
# native OCR / imaging libraries.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
