"""Idle-killed subprocess runner for OCR (cost-optimization Opt 3).

Why a subprocess
----------------
PaddleOCR's native predictor does **not** return its memory to the OS when the
Python object is dropped (measured: ``del`` + ``gc.collect()`` reclaims ~30 MB
of a ~400 MB resident footprint). The only reliable way to give that RAM back
between scans is to terminate the process holding the model.

This runner executes OCR callables in a single dedicated worker process:

* the first scan spawns the worker (which lazily loads the model);
* further scans reuse the warm worker;
* after ``idle_seconds`` with no work the worker is shut down, returning the
  whole model footprint (~0.4-0.5 GB) to the OS;
* the next scan spawns a fresh worker (cold model load).

It also keeps the heavy model out of the web worker process entirely, so the API
process stays lean and an OCR/native crash cannot take the API down.
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _worker_pid(_payload: Any = None) -> int:
    """Trivial worker callable used by tests to observe process lifecycle.

    Defined at module level so it is importable (picklable) by the child
    process. Importing this module does not import PaddleOCR, so the lifecycle
    tests stay fast and model-free.
    """
    return os.getpid()


def _init_worker_logging() -> None:
    """Set up logging inside the OCR worker process.

    The worker is a *separate* process that never runs the app's
    ``configure_logging``, so without this its log records (including the OCR
    engine's "ONNX OCR unavailable / execution error" messages) would be lost —
    OCR failures would surface only as silent empty results.

    To avoid multi-process rotation races on the shared app log files, the worker
    writes to its own dedicated ``ocr-worker.log`` (plus stderr). All OCR engine
    and runner records propagate to the root logger and land there.
    """
    import logging
    import logging.handlers

    try:
        from app.core.config import get_settings

        cfg = get_settings()
        log_dir = cfg.log_dir
        os.makedirs(log_dir, exist_ok=True)
        level = getattr(logging, str(cfg.log_level).upper(), logging.INFO)

        root = logging.getLogger()
        root.setLevel(level)
        # Idempotent: don't double-attach if the initializer somehow runs twice.
        if any(getattr(h, "_ocr_worker", False) for h in root.handlers):
            return

        fmt = logging.Formatter(
            "%(asctime)s - %(name)-22s - %(levelname)-8s - [ocr-worker] %(message)s"
        )
        fh = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "ocr-worker.log"),
            maxBytes=int(cfg.log_max_bytes),
            backupCount=int(cfg.log_backup_count),
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        fh.setLevel(level)
        fh._ocr_worker = True  # type: ignore[attr-defined]
        root.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        sh.setLevel(level)
        sh._ocr_worker = True  # type: ignore[attr-defined]
        root.addHandler(sh)
    except Exception:
        # Logging setup must never break OCR itself.
        pass


class IdleProcessRunner:
    """Run callables in one worker process that is killed after an idle period."""

    def __init__(self, idle_seconds: float) -> None:
        self._idle = idle_seconds
        self._lock = threading.Lock()
        self._executor: Optional[ProcessPoolExecutor] = None
        self._timer: Optional[threading.Timer] = None
        self._inflight = 0

    # -- internal helpers (must hold self._lock) ----------------------------

    def _ensure_executor_locked(self) -> ProcessPoolExecutor:
        if self._executor is None:
            logger.info("ocr_process_runner: spawning worker process")
            # initializer wires logging in the child so OCR engine errors are
            # captured (the worker never runs the app's configure_logging).
            self._executor = ProcessPoolExecutor(
                max_workers=1, initializer=_init_worker_logging
            )
        return self._executor

    def _cancel_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _arm_timer_locked(self) -> None:
        self._cancel_timer_locked()
        if self._idle > 0:
            self._timer = threading.Timer(self._idle, self._maybe_shutdown)
            self._timer.daemon = True
            self._timer.start()

    def _shutdown_executor_locked(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    # -- idle watchdog ------------------------------------------------------

    def _maybe_shutdown(self) -> None:
        with self._lock:
            if self._inflight > 0:
                # Work arrived/queued in the meantime; re-arm and keep the worker.
                self._arm_timer_locked()
                return
            if self._executor is not None:
                logger.info(
                    "ocr_process_runner: idle for %ss, terminating worker (freeing model RAM)",
                    self._idle,
                )
                self._shutdown_executor_locked()

    # -- public API ---------------------------------------------------------

    def submit(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Run ``fn(*args)`` in the worker process and return its result.

        On a broken worker (e.g. a native crash) the pool is reset so the next
        call spawns a fresh process, and the error is propagated to the caller.
        """
        with self._lock:
            executor = self._ensure_executor_locked()
            self._cancel_timer_locked()  # don't let the watchdog fire mid-task
            self._inflight += 1
        try:
            return executor.submit(fn, *args).result()
        except Exception:
            # A broken process pool cannot be reused — drop it so we respawn.
            with self._lock:
                self._shutdown_executor_locked()
            raise
        finally:
            with self._lock:
                self._inflight -= 1
                self._arm_timer_locked()

    def shutdown(self) -> None:
        with self._lock:
            self._cancel_timer_locked()
            self._shutdown_executor_locked()


# Module-level singleton, created on first use from settings. -----------------
_runner: Optional[IdleProcessRunner] = None
_runner_lock = threading.Lock()


def get_runner() -> Optional[IdleProcessRunner]:
    """Return the shared runner, or ``None`` when process isolation is disabled."""
    from app.core.config import get_settings

    cfg = get_settings()
    if not getattr(cfg, "cfg_ocr_process_isolation", True):
        return None

    global _runner
    if _runner is None:
        with _runner_lock:
            if _runner is None:
                _runner = IdleProcessRunner(
                    idle_seconds=float(getattr(cfg, "cfg_ocr_idle_unload_seconds", 300))
                )
    return _runner
