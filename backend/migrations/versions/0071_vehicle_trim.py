"""0071 — vehicle.trim (engine/trim descriptor, shown as "Version" on documents)

Revision ID: 0071
Revises: 0070
Create Date: 2026-08-02 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vehicle",
        sa.Column("trim", sa.String(length=150), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vehicle", "trim")
