"""Application logging — component-scoped, captures everything.

Logs are organised by **deployable component**, not by business domain.
Files (all rotating, in logs/):

  backend-fastapi.log            — everything from the API: every module,
                                   info, data-flow (DEBUG), warnings, SQL.
  backend-fastapi.errors.log     — WARNING/ERROR/CRITICAL with full tracebacks
                                   (a triage mirror of the above).
  backend-fastapi.financial.log  — money trail: payments, invoices, credit
                                   notes, refunds, advances, cash sessions…
                                   (mirrored into backend-fastapi.log too).
  backend-fastapi.http.log       — full request/response data flow: method,
                                   path, query, body, status, timing, request_id.
  infra.log                      — uvicorn, scheduler jobs, migrations,
                                   startup/shutdown, archivers.
  frontend.log                   — browser logs shipped from the SPA
                                   (via POST /api/v1/logs/client).

Pre-deployment posture: level is DEBUG and sensitive-key redaction is OFF, so
we capture literally everything (full bodies, tokens, SQL params). Flip
``REDACT`` to ``True`` and raise the level before production.

Usage (unchanged API):
    from app.core.logging import get_logger
    logger = get_logger("auth.service")
    logger.info("login_success", user_id="3", ip="1.2.3.4")
    logger.exception("unexpected_error", exc=str(e))

Specialised streams:
    from app.core.logging import get_financial_logger, get_infra_logger
    money = get_financial_logger("payment.service")
    money.info("payment_recorded", invoice_id="42", amount_minor=12500)
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any

# Repo backend root (…/backend), so logs land in ONE place no matter which
# directory the server was launched from. logging.py lives at
# backend/app/core/logging.py → parents[2] == backend/.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def resolve_log_dir(log_dir: str) -> str:
    """Anchor a relative log dir to the backend root (absolute paths pass through).

    Without this, ``log_dir="logs"`` resolved against the current working
    directory, so logs scattered into ``backend/logs`` or the repo-root ``logs``
    depending on where uvicorn was started — a real source of "where are my
    logs?" confusion. Used by both the API process and the OCR worker process so
    they always write to the same files.
    """
    p = Path(log_dir)
    return str(p if p.is_absolute() else _BACKEND_ROOT / p)

# ---------------------------------------------------------------------------
# Posture flags (pre-deployment = capture everything)
# ---------------------------------------------------------------------------

#: When True, values under _SENSITIVE_KEYS are masked. Off pre-deployment so we
#: can see real payloads/tokens while building. Turn ON before production.
REDACT = False

_SENSITIVE_KEYS = frozenset(
    {
        "password", "password_hash", "token", "access_token", "refresh_token",
        "secret", "secret_key", "card_number", "cvv", "pin",
    }
)

# ---------------------------------------------------------------------------
# Streams → log files. A "stream" is a stdlib logger name with its own file.
# ---------------------------------------------------------------------------

STREAM_APP = "backend-fastapi"
STREAM_FINANCIAL = "backend-fastapi.financial"
STREAM_HTTP = "backend-fastapi.http"
STREAM_INFRA = "infra"
STREAM_FRONTEND = "frontend"

_STREAM_FILES: dict[str, str] = {
    STREAM_APP: "backend-fastapi.log",
    STREAM_FINANCIAL: "backend-fastapi.financial.log",
    STREAM_HTTP: "backend-fastapi.http.log",
    STREAM_INFRA: "infra.log",
    STREAM_FRONTEND: "frontend.log",
}

_ERRORS_FILE = "backend-fastapi.errors.log"

# Components whose logs are part of the money trail. Matched on the part before
# the first dot, e.g. "payment.service" -> "payment".
_FINANCIAL_BASES = frozenset(
    {
        "payment", "invoice", "credit_note", "advance_payment", "cash_session",
        "refund", "supplier_invoice", "bon_de_retour", "accounting_export",
        "quotation",  # quotations carry priced lines / totals
    }
)

# Components that are runtime/infra rather than request-handling business logic.
_INFRA_BASES = frozenset(
    {
        "app", "infra", "uvicorn", "scheduler", "migrations", "archiver",
        "startup", "lifespan",
    }
)


def _stream_for(component: str) -> str:
    base = component.split(".", 1)[0]
    if component == "http" or base == "http":
        return STREAM_HTTP
    if base in _INFRA_BASES:
        return STREAM_INFRA
    if base in _FINANCIAL_BASES:
        return STREAM_FINANCIAL
    return STREAM_APP


# ---------------------------------------------------------------------------
# Logger wrapper
# ---------------------------------------------------------------------------


class _ComponentLogger:
    """Routes log calls to the right stream logger and prepends the component
    name plus any keyword context to the message.

    Safe to instantiate at import time: the underlying stdlib logger is resolved
    lazily on each call, so handlers configured later by configure_logging() are
    already attached by the time the first real log happens.
    """

    __slots__ = ("_component", "_stream")

    def __init__(self, component: str, stream: str | None = None) -> None:
        self._component = component
        self._stream = stream or _stream_for(component)

    def _fmt(self, msg: str, **kw: Any) -> str:
        if REDACT:
            for key in list(kw):
                if key.lower() in _SENSITIVE_KEYS:
                    kw[key] = "***REDACTED***"
        if kw:
            pairs = "  ".join(f"{k}={v!r}" for k, v in kw.items())
            return f"[{self._component}] {msg}  {pairs}"
        return f"[{self._component}] {msg}"

    def _lg(self) -> logging.Logger:
        return logging.getLogger(self._stream)

    def debug(self, msg: str, **kw: Any) -> None:
        self._lg().debug(self._fmt(msg, **kw), stacklevel=2)

    def info(self, msg: str, **kw: Any) -> None:
        self._lg().info(self._fmt(msg, **kw), stacklevel=2)

    def warning(self, msg: str, **kw: Any) -> None:
        self._lg().warning(self._fmt(msg, **kw), stacklevel=2)

    def error(self, msg: str, **kw: Any) -> None:
        self._lg().error(self._fmt(msg, **kw), stacklevel=2)

    def exception(self, msg: str, **kw: Any) -> None:
        # exc_info is pulled from the active exception automatically.
        self._lg().exception(self._fmt(msg, **kw), stacklevel=2)

    def critical(self, msg: str, **kw: Any) -> None:
        self._lg().critical(self._fmt(msg, **kw), stacklevel=2)


# ---------------------------------------------------------------------------
# Public factories
# ---------------------------------------------------------------------------

_component_loggers: dict[tuple[str, str], _ComponentLogger] = {}


def _cached(component: str, stream: str) -> _ComponentLogger:
    key = (component, stream)
    if key not in _component_loggers:
        _component_loggers[key] = _ComponentLogger(component, stream)
    return _component_loggers[key]


def get_logger(component: str) -> _ComponentLogger:
    """Logger for *component*, auto-routed to the right stream. Import-safe."""
    return _cached(component, _stream_for(component))


def get_financial_logger(component: str) -> _ComponentLogger:
    """Logger that always writes to the financial money trail (and the main
    backend-fastapi.log mirror). Use for explicit money-amount events."""
    return _cached(component, STREAM_FINANCIAL)


def get_infra_logger(component: str) -> _ComponentLogger:
    """Logger for runtime/infra events → infra.log."""
    return _cached(component, STREAM_INFRA)


def get_frontend_logger(component: str = "frontend") -> _ComponentLogger:
    """Logger for browser logs ingested from the SPA → frontend.log."""
    return _cached(component, STREAM_FRONTEND)


# ---------------------------------------------------------------------------
# Startup configuration — call once from main.py lifespan
# ---------------------------------------------------------------------------

_FMT = logging.Formatter(
    fmt="%(asctime)s - %(name)-22s - %(levelname)-8s - %(message)s",
    # No datefmt → Python default includes milliseconds.
)


def _rotating(path: str, max_bytes: int, backup_count: int, level: int) -> logging.handlers.RotatingFileHandler:
    fh = logging.handlers.RotatingFileHandler(
        filename=path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    fh.setFormatter(_FMT)
    fh.setLevel(level)
    return fh


def _has(logger: logging.Logger, cls: type, filename: str | None = None) -> bool:
    for h in logger.handlers:
        if isinstance(h, cls):
            if filename is None:
                return True
            if getattr(h, "baseFilename", "").endswith(filename):
                return True
    return False


def configure_logging(
    log_level: str,
    log_dir: str,
    max_bytes: int,
    backup_count: int,
) -> None:
    """Configure rotating file + console handlers for every component stream.

    Idempotent: duplicate handlers are not added, and ``disabled`` is reset on
    each call (Alembic's fileConfig can flip it on unknown loggers).
    """
    level = getattr(logging, log_level.upper(), logging.DEBUG)

    log_dir = resolve_log_dir(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(_FMT)
    console.setLevel(level)

    # Shared errors mirror — every WARNING+ from app/financial/infra/frontend
    # lands here with its traceback for fast triage.
    errors_path = os.path.join(log_dir, _ERRORS_FILE)

    def _attach_common(lg: logging.Logger, *, with_errors: bool) -> None:
        lg.setLevel(level)
        lg.propagate = False
        lg.disabled = False
        if not _has(lg, logging.StreamHandler) or not any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in lg.handlers
        ):
            lg.addHandler(console)
        if with_errors and not _has(lg, logging.handlers.RotatingFileHandler, _ERRORS_FILE):
            lg.addHandler(_rotating(errors_path, max_bytes, backup_count, logging.WARNING))

    # --- per-stream loggers + their own file ---
    for stream, filename in _STREAM_FILES.items():
        lg = logging.getLogger(stream)
        # http is high-volume and noisy → keep it out of the errors mirror.
        _attach_common(lg, with_errors=(stream != STREAM_HTTP))
        if not _has(lg, logging.handlers.RotatingFileHandler, filename):
            lg.addHandler(_rotating(os.path.join(log_dir, filename), max_bytes, backup_count, level))

    # The financial stream also mirrors into the main backend-fastapi.log so the
    # "everything" file truly has everything.
    financial_lg = logging.getLogger(STREAM_FINANCIAL)
    main_file = os.path.join(log_dir, _STREAM_FILES[STREAM_APP])
    if not _has(financial_lg, logging.handlers.RotatingFileHandler, _STREAM_FILES[STREAM_APP]):
        financial_lg.addHandler(_rotating(main_file, max_bytes, backup_count, level))

    # --- SQLAlchemy data flow → backend-fastapi.log (every query + params) ---
    app_lg = logging.getLogger(STREAM_APP)
    for sa_name in ("sqlalchemy.engine", "sqlalchemy.pool"):
        sa_lg = logging.getLogger(sa_name)
        sa_lg.setLevel(logging.INFO)  # INFO = statements+params; DEBUG = + rows
        sa_lg.propagate = False
        sa_lg.disabled = False
        for h in app_lg.handlers:
            if not any(type(existing) is type(h) and getattr(existing, "baseFilename", None) == getattr(h, "baseFilename", None) for existing in sa_lg.handlers):
                sa_lg.addHandler(h)

    # --- scheduler + migrations + raw-getLogger modules → infra ---
    # Note: uvicorn's own loggers are configured via uvicorn_log_config.json
    # (--log-config) which writes to logs/infra.log, so they are intentionally
    # NOT wired here to avoid duplicate handlers on the same file.
    infra_lg = logging.getLogger(STREAM_INFRA)
    _infra_named = (
        "apscheduler", "apscheduler.scheduler", "apscheduler.executors.default",
        "app.modules.notification.scheduler",
        "app.modules.media.archiver",
        "app.modules.documents.archiver",
        "alembic", "alembic.runtime.migration",
    )
    for name in _infra_named:
        nl = logging.getLogger(name)
        nl.setLevel(level)
        nl.propagate = False
        nl.disabled = False
        for h in infra_lg.handlers:
            if not any(type(existing) is type(h) and getattr(existing, "baseFilename", None) == getattr(h, "baseFilename", None) for existing in nl.handlers):
                nl.addHandler(h)

    # --- other modules using raw logging.getLogger(__name__) → app stream ---
    for name in (
        "app.modules.ocr.engine",
        "app.modules.ocr.process_runner",
        "app.modules.notification.adapter",
    ):
        nl = logging.getLogger(name)
        nl.setLevel(level)
        nl.propagate = False
        nl.disabled = False
        for h in app_lg.handlers:
            if not any(type(existing) is type(h) and getattr(existing, "baseFilename", None) == getattr(h, "baseFilename", None) for existing in nl.handlers):
                nl.addHandler(h)
