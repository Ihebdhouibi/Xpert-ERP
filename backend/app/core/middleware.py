"""
Request-scoped middleware.

- RequestIDMiddleware: injects X-Request-ID header and binds request_id
  to the structlog context for the duration of the request.
  Also logs HTTP request/response at INFO level (method, path, status, duration_ms).
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("http")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a unique X-Request-ID.
    The ID is echoed in the response header and bound into structlog contextvars
    so every log line emitted during that request carries request_id automatically.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
