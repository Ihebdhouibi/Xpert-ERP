"""
Request-scoped middleware.

RequestIDMiddleware injects an X-Request-ID header and logs the **full**
request/response data-flow to the http stream (logs/backend-fastapi.http.log):
method, path, query, client, headers, and bodies for textual payloads.

Pre-deployment posture: bodies are captured in full (up to a size cap) with no
redaction. Binary / multipart / streaming / file responses are logged as
metadata only so uploads and downloads (PDFs, presigned files) keep working.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("http")

# Cap how many body bytes we render into the log line.
_MAX_BODY = 16 * 1024
# Content types whose bodies are safe/useful to capture as text.
_TEXTUAL = (
    "application/json",
    "application/xml",
    "application/x-www-form-urlencoded",
    "text/",
)


def _is_textual(content_type: str) -> bool:
    ct = content_type.lower()
    if "multipart/form-data" in ct:
        return False
    return any(t in ct for t in _TEXTUAL)


def _truncate(raw: bytes) -> str:
    clipped = raw[:_MAX_BODY]
    text = clipped.decode("utf-8", "replace")
    if len(raw) > _MAX_BODY:
        text += f"…(truncated, {len(raw)} bytes total)"
    return text


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        # ---- request body (textual only; cached so the endpoint can re-read) ----
        req_ct = request.headers.get("content-type", "")
        req_len = int(request.headers.get("content-length") or 0)
        req_body: str | None = None
        if req_len and _is_textual(req_ct):
            try:
                req_body = _truncate(await request.body())
            except Exception:
                req_body = "<unreadable>"
        elif req_len:
            req_body = f"<{req_ct or 'binary'} {req_len} bytes — not captured>"

        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) or None,
            client=request.client.host if request.client else None,
            headers=dict(request.headers),
            body=req_body,
            request_id=request_id,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                "[UNHANDLED] request_error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                request_id=request_id,
                exc_type=type(exc).__name__,
                exc=str(exc),
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        resp_ct = response.headers.get("content-type", "")

        # ---- response body: capture+rebuild only for textual payloads ----
        if _is_textual(resp_ct):
            chunks = [chunk async for chunk in response.body_iterator]
            full = b"".join(chunks)
            logger.info(
                "[TIMING] request_completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                body=_truncate(full),
            )
            rebuilt = Response(
                content=full,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            rebuilt.background = response.background
            return rebuilt

        # Binary / streaming / file response — log metadata, return untouched.
        logger.info(
            "[TIMING] request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            content_type=resp_ct or None,
            body="<non-textual — not captured>",
        )
        return response
