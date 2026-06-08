"""0037 — add repair_order.diagnosis + diagnosis_completed_at

Stores the diagnosis answers (D1..D5 + notes) entered during the diagnosis step.

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-08 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repair_order",
        sa.Column("diagnosis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "repair_order",
        sa.Column("diagnosis_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repair_order", "diagnosis_completed_at")
    op.drop_column("repair_order", "diagnosis")
