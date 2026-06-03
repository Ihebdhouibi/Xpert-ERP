"""
Health check router.
GET /api/v1/health — liveness probe used by docker-compose, CI, and the React app.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger("health.router")
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
    )
