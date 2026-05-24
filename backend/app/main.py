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

    # Run Alembic migrations on every startup (safe — only applies pending ones)
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        from pathlib import Path

        alembic_cfg = AlembicConfig(str(Path(__file__).parent.parent / "alembic.ini"))
        # Use sync URL (psycopg2) for Alembic
        sync_url = settings.database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://", 1
        )
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        command.upgrade(alembic_cfg, "head")
        logger.info("migrations_applied")
    except Exception as exc:
        logger.error("migrations_failed", error=str(exc))
        raise

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
    from app.modules.sequence.router import router as sequence_router
    from app.modules.quotation.router import router as quotation_router
    from app.modules.invoice.router import router as invoice_router
    from app.modules.pdf.router import router as pdf_router
    from app.modules.payment.router import router as payment_router
    from app.modules.advance_payment.router import router as advance_payment_router
    from app.modules.cash_session.router import router as cash_session_router
    from app.modules.credit_note.router import router as credit_note_router, refund_router

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(vehicles_router, prefix="/api/v1")
    app.include_router(customer_router, prefix="/api/v1")
    app.include_router(sequence_router, prefix="/api/v1")
    app.include_router(quotation_router, prefix="/api/v1")
    app.include_router(invoice_router, prefix="/api/v1")
    app.include_router(pdf_router, prefix="/api/v1")
    app.include_router(payment_router, prefix="/api/v1")
    app.include_router(advance_payment_router, prefix="/api/v1")
    app.include_router(cash_session_router, prefix="/api/v1")
    app.include_router(credit_note_router, prefix="/api/v1")
    app.include_router(refund_router, prefix="/api/v1")

    return app


app = create_app()
