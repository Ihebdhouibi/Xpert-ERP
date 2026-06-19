"""Client log ingest — receives browser logs from the SPA and writes them to
the frontend component stream (logs/frontend.log).

Intentionally unauthenticated: front-end errors can happen before/around login,
and we want to capture them all in the pre-deployment phase. A batch-size cap
keeps it from being abused.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.logging import get_frontend_logger

router = APIRouter(prefix="/logs", tags=["logs"])

log = get_frontend_logger("frontend")

_LEVELS = {"debug", "info", "warn", "warning", "error"}


class ClientLogEntry(BaseModel):
    level: str = "info"
    message: str = ""
    # Free-form structured context (component, action, payload, status, …).
    context: dict | None = None
    timestamp: str | None = None
    url: str | None = None
    user_agent: str | None = None
    stack: str | None = None


class ClientLogBatch(BaseModel):
    entries: list[ClientLogEntry] = Field(default_factory=list, max_length=200)


@router.post("/client", status_code=204)
async def ingest_client_logs(batch: ClientLogBatch, request: Request) -> None:
    client_ip = request.client.host if request.client else None
    for e in batch.entries:
        level = e.level.lower()
        if level not in _LEVELS:
            level = "info"
        emit = getattr(log, "warning" if level == "warn" else level)
        emit(
            e.message or "client_log",
            ts=e.timestamp,
            url=e.url,
            ip=client_ip,
            ua=e.user_agent,
            stack=e.stack,
            **(e.context or {}),
        )
