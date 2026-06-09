"""0040 — add opening_float to cash_session

A cash drawer starts the day with a change fund (the "fond de caisse").
Without it, the expected cash on close was computed as cash payments only,
so the reconciliation difference was wrong whenever a float was present.

Adds cash_session.opening_float (minor units, default 0). Existing rows get
0, preserving their previous behaviour.

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-09 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cash_session",
        sa.Column(
            "opening_float",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("cash_session", "opening_float")
