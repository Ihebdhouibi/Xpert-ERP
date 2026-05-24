"""
Xpert-ERP FastAPI application factory and lifespan.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware
from app.core.redis import close_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(
        log_level=settings.log_level,
        log_dir=settings.log_dir,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )
    logger = get_logger("app")
    logger.info("startup", version=settings.app_version, environment=settings.environment)
    yield
    await close_redis()
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware (order matters: outer-most first)
    # ------------------------------------------------------------------
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    from app.modules.health.router import router as health_router
    from app.modules.auth.router import router as auth_router
    from app.modules.rbac.router import router as users_router
    from app.modules.documents.router import router as documents_router
    from app.modules.vehicles.router import router as vehicles_router
    from app.modules.customer.router import router as customer_router
    from app.modules.repair_order.router import router as repair_order_router
    from app.modules.repair_order.time_entry_router import router as time_entry_router
    from app.modules.parts.router import router as parts_router
    from app.modules.parts.stock_router import router as stock_router

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(vehicles_router, prefix="/api/v1")
    app.include_router(customer_router, prefix="/api/v1")
    app.include_router(repair_order_router, prefix="/api/v1")
    app.include_router(time_entry_router, prefix="/api/v1/repair-orders")
    app.include_router(parts_router, prefix="/api/v1")
    app.include_router(stock_router, prefix="/api/v1")

    return app


app = create_app()
