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
    op.add_column(
        "ro_part_line",
        sa.Column("remise_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "ro_part_line",
        sa.Column("tva_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("ro_part_line", "tva_pct")
    op.drop_column("ro_part_line", "remise_pct")
