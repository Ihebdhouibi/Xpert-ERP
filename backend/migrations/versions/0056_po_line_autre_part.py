"""purchase_order_line: allow "Autre" (uncatalogued) lines

Make part_id nullable and add a free-text label so a PO line can reference a
part that isn't in the catalogue yet (an "Autre" line). The line is reassigned
to a real part once the BL is validated.

Revision ID: 0056
Revises: 0055
"""
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE purchase_order_line ALTER COLUMN part_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE purchase_order_line ADD COLUMN IF NOT EXISTS label VARCHAR(255)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE purchase_order_line DROP COLUMN IF EXISTS label")
    # Not restoring NOT NULL: rows created as "Autre" may have a null part_id.
