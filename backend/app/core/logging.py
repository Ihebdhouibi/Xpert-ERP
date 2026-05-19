"""
Per-component structured logging with structlog.

Usage:
    from app.core.logging import get_logger
    logger = get_logger("auth")
    logger.info("login_success", user_id=str(user.id), ip=ip_address)

Each component writes to logs/<component>.log (rotating) and to stdout.
Sensitive fields (password, token, secret, card) are redacted automatically.
"""

import logging
import logging.handlers
import os
import sys
from typing import Any

import structlog

_SENSITIVE_KEYS = frozenset(
    {"password", "password_hash", "token", "access_token", "refresh_token",
     "secret", "secret_key", "card_number", "cvv", "pin"}
)


def _redact_sensitive(logger: Any, method: str, event_dict: dict) -> dict:  # noqa: ANN401
    """structlog processor that redacts sensitive keys from log entries."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def _setup_file_handler(component: str, log_dir: str, max_bytes: int, backup_count: int) -> logging.Handler:
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f"{component}.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def configure_logging(log_level: str, log_dir: str, max_bytes: int, backup_count: int) -> None:
    """
    Call once at application startup (in main.py lifespan).
    Configures structlog with JSON rendering, timestamp, level, and redaction.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)

    # Per-component file handlers registered on demand in get_logger()
    # Store config for later use
    _logging_config["log_dir"] = log_dir
    _logging_config["max_bytes"] = max_bytes
    _logging_config["backup_count"] = backup_count
    _logging_config["formatter"] = formatter
    _logging_config["level"] = level


_logging_config: dict[str, Any] = {}
_component_loggers: dict[str, Any] = {}


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog bound logger for the given component name.
    Creates and registers a per-component rotating file handler on first call.
    """
    if component not in _component_loggers:
        stdlib_logger = logging.getLogger(component)
        stdlib_logger.setLevel(_logging_config.get("level", logging.INFO))

        if _logging_config.get("log_dir") and not any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            for h in stdlib_logger.handlers
        ):
            file_handler = _setup_file_handler(
                component=component,
                log_dir=_logging_config["log_dir"],
                max_bytes=_logging_config["max_bytes"],
                backup_count=_logging_config["backup_count"],
            )
            if "formatter" in _logging_config:
                file_handler.setFormatter(_logging_config["formatter"])
            stdlib_logger.addHandler(file_handler)

        _component_loggers[component] = structlog.get_logger(component)

    return _component_loggers[component]  # type: ignore[return-value]
