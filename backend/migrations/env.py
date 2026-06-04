"""
Alembic env.py — dual-mode migration environment.

Two execution paths:
  1. CLI (`alembic upgrade head`): asyncio.run() with WindowsSelectorEventLoopPolicy
     on Windows so asyncpg works (ProactorEventLoop breaks asyncpg on Windows).
  2. App lifespan: caller passes a sync connection via
     `config.attributes["connection"]` (obtained from `await conn.run_sync(...)`).
     No asyncio.run() needed — avoids nested-event-loop errors.
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

# Load .env from backend/ or project root, whichever exists first
for _dotenv in (
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent.parent.parent / ".env",
):
    if _dotenv.exists():
        load_dotenv(_dotenv, override=False)
        break

from app.core.database import Base  # noqa: E402

# Import all models so Alembic autogenerate can detect them
import app.modules.auth.models  # noqa: F401, E402
import app.modules.audit.models  # noqa: F401, E402
import app.modules.customer.models  # noqa: F401, E402
import app.modules.ocr.models  # noqa: F401, E402

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False is critical: without it, the default True
    # causes Python to set logger.disabled=True on every logger that isn't listed
    # in alembic.ini (i.e. all our "auth", "sales", "http" group loggers), which
    # silences all application logging for the entire server run.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Resolve async URL — must use postgresql+asyncpg://
_raw_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
if _raw_url.startswith("postgresql://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql+psycopg2://"):
    _async_url = _raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
else:
    _async_url = _raw_url  # already asyncpg

if not _async_url.startswith("postgresql"):
    raise RuntimeError(f"Could not resolve a PostgreSQL DATABASE_URL (got: {_raw_url!r})")

config.set_main_option("sqlalchemy.url", _async_url)


def do_run_migrations(sync_connection) -> None:
    """Run pending migrations against *sync_connection* (sync wrapper from run_sync)."""
    context.configure(connection=sync_connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Generate SQL script without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    """CLI path: create a fresh asyncpg engine and run migrations."""
    engine = create_async_engine(_async_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    # Path 1: caller supplied a sync connection (app lifespan via run_sync)
    pre_conn = context.config.attributes.get("connection", None)
    if pre_conn is not None:
        do_run_migrations(pre_conn)
        return

    # Path 2: CLI — asyncpg requires SelectorEventLoop on Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
