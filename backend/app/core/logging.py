"""Application logging — pure stdlib, grouped by business domain.

Log files (all rotating, in logs/):
  auth.log         — authentication, authorization, RBAC
  sales.log        — customers, quotations, invoices, payments, credit notes
  workshop.log     — repair orders, parts, vehicles, inspections
  procurement.log  — suppliers, purchase orders, supplier invoices
  system.log       — startup, config, sequences, documents, audit, media, KPI
  http.log         — every inbound HTTP request/response

Usage (unchanged API):
  from app.core.logging import get_logger
  logger = get_logger("auth.service")
  logger.info("login_success", user_id=str(user.id), ip="1.2.3.4")
  logger.error("unexpected_error", exc=str(e))
"""

import logging
import logging.handlers
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Sensitive-key redaction
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset(
    {
        "password", "password_hash", "token", "access_token", "refresh_token",
        "secret", "secret_key", "card_number", "cvv", "pin",
    }
)

# ---------------------------------------------------------------------------
# Component -> group mapping
# ---------------------------------------------------------------------------

_GROUP: dict[str, str] = {
    # auth
    "auth":             "auth",
    "auth.router":      "auth",
    "auth.service":     "auth",
    "rbac":             "auth",
    "rbac.router":      "auth",
    "rbac.service":     "auth",
    # sales
    "customer":                "sales",
    "customer.router":         "sales",
    "customer.service":        "sales",
    "customer.credit":         "sales",
    "quotation":               "sales",
    "quotation.router":        "sales",
    "quotation.service":       "sales",
    "invoice":                 "sales",
    "invoice.router":          "sales",
    "invoice.service":         "sales",
    "payment":                 "sales",
    "payment.router":          "sales",
    "payment.service":         "sales",
    "advance_payment":         "sales",
    "advance_payment.router":  "sales",
    "advance_payment.service": "sales",
    "credit_note":             "sales",
    "credit_note.router":      "sales",
    "credit_note.service":     "sales",
    "cash_session":            "sales",
    "cash_session.router":     "sales",
    "cash_session.service":    "sales",
    # workshop
    "repair_order":                    "workshop",
    "repair_order.router":             "workshop",
    "repair_order.service":            "workshop",
    "repair_order.time_entry":         "workshop",
    "repair_order.time_entry_router":  "workshop",
    "inspection":                      "workshop",
    "inspection.router":               "workshop",
    "inspection.service":              "workshop",
    "parts":                           "workshop",
    "parts.router":                    "workshop",
    "parts.service":                   "workshop",
    "parts.stock":                     "workshop",
    "parts.stock_router":              "workshop",
    "vehicles":                        "workshop",
    "vehicles.router":                 "workshop",
    "vehicles.service":                "workshop",
    # procurement
    "supplier":                  "procurement",
    "supplier.router":           "procurement",
    "supplier.service":          "procurement",
    "purchase_order":            "procurement",
    "purchase_order.router":     "procurement",
    "purchase_order.service":    "procurement",
    "supplier_invoice":          "procurement",
    "supplier_invoice.router":   "procurement",
    "supplier_invoice.service":  "procurement",
    "bon_de_retour":             "procurement",
    "bon_de_retour.router":      "procurement",
    "bon_de_retour.service":     "procurement",
    # system
    "app":                        "system",
    "health":                     "system",
    "health.router":              "system",
    "config":                     "system",
    "config.router":              "system",
    "config.service":             "system",
    "sequence":                   "system",
    "sequence.router":            "system",
    "sequence.service":           "system",
    "documents":                  "system",
    "documents.router":           "system",
    "documents.service":          "system",
    "documents.storage":          "system",
    "accounting_export":          "system",
    "accounting_export.router":   "system",
    "accounting_export.service":  "system",
    "notification":               "system",
    "notification.router":        "system",
    "notification.service":       "system",
    "media":                      "system",
    "media.router":               "system",
    "media.service":              "system",
    "media.storage":              "system",
    "kpi":                        "system",
    "kpi.router":                 "system",
    "kpi.service":                "system",
    "pdf":                        "system",
    "pdf.router":                 "system",
    "pdf.service":                "system",
    "ocr":                        "system",
    "ocr.router":                 "system",
    "ocr.service":                "system",
    "ocr.engine":                 "system",
    "app.modules.ocr.engine":     "system",
    "audit":                      "system",
    # http
    "http": "http",
}

_ALL_GROUPS = ("auth", "sales", "workshop", "procurement", "system", "http")

# ---------------------------------------------------------------------------
# Logger wrapper
# ---------------------------------------------------------------------------


class _ComponentLogger:
    """
    Thin wrapper that routes log calls to the correct group logger and prepends
    the component name plus any keyword context to the message.

    Safe to instantiate at module import time. The underlying stdlib logger is
    resolved lazily on each call so it already has its handlers by the time
    the first real log call is made (after configure_logging() runs at startup).
    """

    __slots__ = ("_component", "_group")

    def __init__(self, component: str) -> None:
        self._component = component
        self._group = _GROUP.get(component, "system")

    def _fmt(self, msg: str, **kw: Any) -> str:
        for key in list(kw):
            if key.lower() in _SENSITIVE_KEYS:
                kw[key] = "***REDACTED***"
        if kw:
            pairs = "  ".join(f"{k}={v!r}" for k, v in kw.items())
            return f"[{self._component}] {msg}  {pairs}"
        return f"[{self._component}] {msg}"

    def _lg(self) -> logging.Logger:
        return logging.getLogger(self._group)

    def debug(self, msg: str, **kw: Any) -> None:
        self._lg().debug(self._fmt(msg, **kw), stacklevel=2)

    def info(self, msg: str, **kw: Any) -> None:
        self._lg().info(self._fmt(msg, **kw), stacklevel=2)

    def warning(self, msg: str, **kw: Any) -> None:
        self._lg().warning(self._fmt(msg, **kw), stacklevel=2)

    def error(self, msg: str, **kw: Any) -> None:
        self._lg().error(self._fmt(msg, **kw), stacklevel=2)

    def exception(self, msg: str, **kw: Any) -> None:
        self._lg().exception(self._fmt(msg, **kw), stacklevel=2)

    def critical(self, msg: str, **kw: Any) -> None:
        self._lg().critical(self._fmt(msg, **kw), stacklevel=2)


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_component_loggers: dict[str, _ComponentLogger] = {}


def get_logger(component: str) -> _ComponentLogger:
    """Return a logger for *component*. Safe to call at module import time."""
    if component not in _component_loggers:
        _component_loggers[component] = _ComponentLogger(component)
    return _component_loggers[component]


# ---------------------------------------------------------------------------
# Startup configuration — call once from main.py lifespan
# ---------------------------------------------------------------------------


def configure_logging(
    log_level: str,
    log_dir: str,
    max_bytes: int,
    backup_count: int,
) -> None:
    """Configure rotating file + console handlers for all log groups.

    Safe to call more than once (hot-reload / test setup):
    - Duplicate handlers are not added.
    - logger.disabled is explicitly reset so Alembic's fileConfig
      (which sets disabled=True on unknown loggers by default) cannot
      silence our handlers even when called between two configure_logging
      calls.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Format matches the reference project: timestamp with ms, logger name, level, message
    # e.g.  2026-06-04 12:34:56,789 - auth - INFO - [auth.service] login_attempt  user_id='3'
    fmt = logging.Formatter(
        fmt="%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s",
        # No datefmt → Python default includes milliseconds: "2026-06-04 12:34:56,789"
    )

    os.makedirs(log_dir, exist_ok=True)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    console.setLevel(level)

    for group in _ALL_GROUPS:
        lg = logging.getLogger(group)
        lg.setLevel(level)
        lg.propagate = False  # don't bubble to root logger
        lg.disabled = False   # undo any disable set by alembic fileConfig

        # Console handler (add once — share the single instance)
        if not any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            for h in lg.handlers
        ):
            lg.addHandler(console)

        # Rotating file handler (add once)
        if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in lg.handlers):
            fh = logging.handlers.RotatingFileHandler(
                filename=os.path.join(log_dir, f"{group}.log"),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            fh.setLevel(level)
            lg.addHandler(fh)

    # ------------------------------------------------------------------
    # Wire uvicorn's own loggers to logs/uvicorn.log so all startup
    # messages, access lines, and tracebacks are captured regardless of
    # whether uvicorn was started with --log-config.
    # ------------------------------------------------------------------
    uvicorn_file = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, "uvicorn.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    uvicorn_file.setFormatter(fmt)
    uvicorn_file.setLevel(logging.DEBUG)

    for uv_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_lg = logging.getLogger(uv_name)
        uv_lg.setLevel(logging.DEBUG)
        uv_lg.disabled = False
        if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in uv_lg.handlers):
            uv_lg.addHandler(uvicorn_file)

    # ------------------------------------------------------------------
    # Some internal modules use stdlib logging.getLogger(__name__) directly
    # instead of get_logger().  Point their loggers at the system group
    # handlers so their output still lands in system.log.
    # ------------------------------------------------------------------
    system_lg = logging.getLogger("system")
    for raw_name in ("app.modules.ocr.engine",):
        raw_lg = logging.getLogger(raw_name)
        raw_lg.setLevel(level)
        raw_lg.propagate = False
        raw_lg.disabled = False
        for h in system_lg.handlers:
            if not any(type(existing) is type(h) for existing in raw_lg.handlers):
                raw_lg.addHandler(h)
