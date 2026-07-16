"""Make repair_order.description nullable — no longer mandatory at creation.

Revision ID: 0063
Revises: 0062
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("repair_order", "description", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE repair_order SET description = '' WHERE description IS NULL")
    op.alter_column("repair_order", "description", existing_type=sa.Text(), nullable=False)
