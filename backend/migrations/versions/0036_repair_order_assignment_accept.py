"""0036 — add repair_order.assignment_accepted_at

Tracks when an assigned mechanic (or a secretary on their behalf) accepts the job.

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-08 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repair_order",
        sa.Column("assignment_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repair_order", "assignment_accepted_at")
