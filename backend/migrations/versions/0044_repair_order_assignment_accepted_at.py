"""0044 — add repair_order.assignment_accepted_at (idempotent backfill)

This column was introduced in migration 0036 but was skipped on databases that
had already recorded version '0036' from the previous numbering scheme
(bon_de_retour_extras).  Uses IF NOT EXISTS so it is safe on both affected
databases and any fresh install where 0036 already ran cleanly.

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-20 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE repair_order"
        " ADD COLUMN IF NOT EXISTS assignment_accepted_at TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE repair_order"
        " DROP COLUMN IF EXISTS assignment_accepted_at"
    )
