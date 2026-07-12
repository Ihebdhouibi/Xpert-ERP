"""Add service_invoice to document_category_enum

Revision ID: 0060
Revises: 0059
Create Date: 2026-07-09
"""
from __future__ import annotations

from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE outside a transaction block.
    # Alembic runs this in autocommit mode when execute_in_autocommit=True isn't
    # available; use a raw connection to issue it outside the current transaction.
    op.execute("COMMIT")
    op.execute(
        "ALTER TYPE document_category_enum ADD VALUE IF NOT EXISTS 'service_invoice'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    pass
