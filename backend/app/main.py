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

    from app.modules.notification.scheduler import configure_scheduler
    from app.modules.media.archiver import register_archiver_job
    notification_scheduler = configure_scheduler()
    register_archiver_job(notification_scheduler)
    notification_scheduler.start()

    # Run Alembic migrations on every startup (safe — only applies pending ones)
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        from pathlib import Path

        backend_dir = Path(__file__).parent.parent
        alembic_cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
        # Resolve script_location relative to the backend dir, not CWD
        alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))
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

    # Seed system notification templates (idempotent)
    try:
        from app.core.database import AsyncSessionFactory
        from app.modules.notification.templates_seed import seed_templates
        async with AsyncSessionFactory() as seed_db:
            await seed_templates(seed_db)
        logger.info("notification_templates_seeded")
    except Exception as exc:
        logger.warning("notification_templates_seed_failed", error=str(exc))

    yield
    notification_scheduler.shutdown(wait=False)
    await close_redis()
    logger.info("shutdown")


def create_app() -> FastAPI:
    _is_dev = settings.environment not in ("production", "staging")
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/v1/docs" if _is_dev else None,
        redoc_url="/api/v1/redoc" if _is_dev else None,
        openapi_url="/api/v1/openapi.json" if _is_dev else None,
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
    from app.modules.sequence.router import router as sequence_router
    from app.modules.quotation.router import router as quotation_router
    from app.modules.invoice.router import router as invoice_router
    from app.modules.pdf.router import router as pdf_router
    from app.modules.payment.router import router as payment_router
    from app.modules.advance_payment.router import router as advance_payment_router
    from app.modules.cash_session.router import router as cash_session_router
    from app.modules.credit_note.router import router as credit_note_router, refund_router
    from app.modules.supplier.router import router as supplier_router
    from app.modules.purchase_order.router import router as purchase_order_router
    from app.modules.supplier_invoice.router import router as supplier_invoice_router
    from app.modules.notification.router import router as notification_router
    from app.modules.inspection.router import router as inspection_router
    from app.modules.media.router import router as media_router
    from app.modules.kpi.router import router as kpi_router
    from app.modules.accounting_export.router import router as accounting_export_router
    from app.modules.config.router import router as config_router

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
    app.include_router(sequence_router, prefix="/api/v1")
    app.include_router(quotation_router, prefix="/api/v1")
    app.include_router(invoice_router, prefix="/api/v1")
    app.include_router(pdf_router, prefix="/api/v1")
    app.include_router(payment_router, prefix="/api/v1")
    app.include_router(advance_payment_router, prefix="/api/v1")
    app.include_router(cash_session_router, prefix="/api/v1")
    app.include_router(credit_note_router, prefix="/api/v1")
    app.include_router(refund_router, prefix="/api/v1")
    app.include_router(supplier_router, prefix="/api/v1")
    app.include_router(purchase_order_router, prefix="/api/v1")
    app.include_router(supplier_invoice_router, prefix="/api/v1")
    app.include_router(notification_router, prefix="/api/v1")
    app.include_router(inspection_router, prefix="/api/v1")
    app.include_router(media_router, prefix="/api/v1")
    app.include_router(kpi_router, prefix="/api/v1")
    app.include_router(accounting_export_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")

    return app


app = create_app()
