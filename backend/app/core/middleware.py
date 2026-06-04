"""
Request-scoped middleware.

- RequestIDMiddleware: injects X-Request-ID header and logs every
  HTTP request/response at INFO level with method, path, status, and
  duration — mirroring the reference project's [TIMING] lines.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("http")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a unique X-Request-ID echoed in the response
    header.  Logs request receipt and response with timing.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
        )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "[TIMING] request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
