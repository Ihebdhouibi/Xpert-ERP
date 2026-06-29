"""supplier delivery note (Bon de livraison) tables

Traceability record for a received supplier BL, linked to a purchase order.
Header carries the bl_number (correlation key) + document link; lines map to PO
lines. Created with raw SQL (idempotent) per project migration conventions.

Revision ID: 0057
Revises: 0056
"""
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS supplier_delivery_note (
            id BIGSERIAL PRIMARY KEY,
            public_id UUID NOT NULL UNIQUE,
            garage_id BIGINT NOT NULL,
            purchase_order_id BIGINT NOT NULL
                REFERENCES purchase_order(id) ON DELETE RESTRICT,
            supplier_id BIGINT NOT NULL,
            bl_number VARCHAR(100),
            bl_date DATE,
            document_id BIGINT,
            status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
            has_discrepancy BOOLEAN NOT NULL DEFAULT false,
            notes TEXT,
            received_by BIGINT,
            received_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_sdn_garage_supplier_blnumber
                UNIQUE (garage_id, supplier_id, bl_number)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sdn_garage_po "
        "ON supplier_delivery_note (garage_id, purchase_order_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS supplier_delivery_note_line (
            id BIGSERIAL PRIMARY KEY,
            supplier_delivery_note_id BIGINT NOT NULL
                REFERENCES supplier_delivery_note(id) ON DELETE CASCADE,
            po_line_id BIGINT,
            part_id BIGINT,
            description VARCHAR(512),
            quantity NUMERIC(12, 3) NOT NULL DEFAULT 0,
            unit_price_ht BIGINT,
            match_flag VARCHAR(20) NOT NULL DEFAULT 'ok'
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sdn_line_sdn "
        "ON supplier_delivery_note_line (supplier_delivery_note_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS supplier_delivery_note_line")
    op.execute("DROP TABLE IF EXISTS supplier_delivery_note")
