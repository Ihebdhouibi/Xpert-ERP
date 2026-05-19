"""
Request-scoped middleware.

- RequestIDMiddleware: injects X-Request-ID header and binds request_id
  to the structlog context for the duration of the request.
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("app")


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

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
