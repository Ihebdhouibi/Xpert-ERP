"""supplier_delivery_note_line: BL-captured fields (code, PU brut/net, montant)

Adds columns that store the supplier BL's own line values, so a delivery note
line is recorded field-by-field (not just the PO-derived values).

Revision ID: 0058
Revises: 0057
"""
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE supplier_delivery_note_line "
        "ADD COLUMN IF NOT EXISTS code VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE supplier_delivery_note_line ADD COLUMN IF NOT EXISTS pu_brut BIGINT"
    )
    op.execute(
        "ALTER TABLE supplier_delivery_note_line ADD COLUMN IF NOT EXISTS pu_net BIGINT"
    )
    op.execute(
        "ALTER TABLE supplier_delivery_note_line "
        "ADD COLUMN IF NOT EXISTS montant_ht BIGINT"
    )


def downgrade() -> None:
    for col in ("code", "pu_brut", "pu_net", "montant_ht"):
        op.execute(
            f"ALTER TABLE supplier_delivery_note_line DROP COLUMN IF EXISTS {col}"
        )
