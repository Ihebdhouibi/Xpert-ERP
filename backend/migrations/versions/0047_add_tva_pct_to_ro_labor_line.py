"""Add tva_pct column to ro_labor_line.

Labor lines previously had no VAT column — amounts were stored as HT.
This migration adds tva_pct (default 20.0) to the table.
Existing rows are left untouched (skip backfill as requested).

Revision ID: 0047
Revises: 0046
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ro_labor_line",
        sa.Column(
            "tva_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="20.00",
        ),
    )


def downgrade() -> None:
    op.drop_column("ro_labor_line", "tva_pct")
