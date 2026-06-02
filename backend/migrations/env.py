"""
Alembic env.py — synchronous migration environment (psycopg2).

Uses a sync engine so Alembic works reliably on all platforms including
Windows where asyncpg + asyncio has known connection-reset issues.
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

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
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Build sync URL: swap asyncpg dialect for psycopg2
_raw_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
_sync_url = _raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
if not _sync_url.startswith("postgresql"):
    raise RuntimeError(f"Could not resolve a PostgreSQL DATABASE_URL (got: {_raw_url!r})")
config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url", ""))
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
