"""0041 — add remise_pct and tva_pct columns to ro_part_line

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-07 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ro_part_line ADD COLUMN IF NOT EXISTS"
        " remise_pct NUMERIC(5, 2) NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE ro_part_line ADD COLUMN IF NOT EXISTS"
        " tva_pct NUMERIC(5, 2) NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE ro_part_line DROP COLUMN IF EXISTS tva_pct")
    op.execute("ALTER TABLE ro_part_line DROP COLUMN IF EXISTS remise_pct")
