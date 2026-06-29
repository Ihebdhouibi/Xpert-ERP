"""supplier-document foundation: BL category + supplier/PO owner types

Additive enum values only (no data migration, no removals):
- document_category_enum  += 'supplier_delivery_note'  (Bon de livraison)
- owner_entity_type_enum  += 'supplier'                (Fournisseur)
- owner_entity_type_enum  += 'purchase_order'          (Bon de commande)

Revision ID: 0055
Revises: 0054
"""
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL 12+ allows `ALTER TYPE ... ADD VALUE` inside a transaction as
    # long as the new value is not *used* in the same transaction (we only add).
    # IF NOT EXISTS keeps the migration idempotent.
    op.execute(
        "ALTER TYPE document_category_enum ADD VALUE IF NOT EXISTS "
        "'supplier_delivery_note'"
    )
    op.execute(
        "ALTER TYPE owner_entity_type_enum ADD VALUE IF NOT EXISTS 'supplier'"
    )
    op.execute(
        "ALTER TYPE owner_entity_type_enum ADD VALUE IF NOT EXISTS "
        "'purchase_order'"
    )


def downgrade() -> None:
    # PostgreSQL cannot drop a value from an enum type without recreating it.
    # The added values are inert when unused, so downgrade is intentionally a
    # no-op (recreating the enum + remapping rows is out of scope for a rollback).
    pass
