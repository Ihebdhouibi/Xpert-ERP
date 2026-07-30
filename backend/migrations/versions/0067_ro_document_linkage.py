"""0067 — link delivery_note and invoice to their originating repair order, and
prevent more than one active (non-cancelled) document of each type per RO.

Revision ID: 0067
Revises: 0066
Create Date: 2026-07-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- delivery_note: add repair_order_id FK (new column) ---
    op.add_column(
        "delivery_note",
        sa.Column("repair_order_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dn_repair_order_id",
        "delivery_note",
        "repair_order",
        ["repair_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_dn_repair_order_id", "delivery_note", ["repair_order_id"])
    # Only one active (non-cancelled) delivery note per repair order.
    op.execute("""
        CREATE UNIQUE INDEX ux_dn_repair_order_active
        ON delivery_note (repair_order_id)
        WHERE repair_order_id IS NOT NULL AND status != 'cancelled'
    """)

    # --- invoice: repair_order_id existed as a bare column — give it a real FK ---
    op.create_foreign_key(
        "fk_invoice_repair_order_id",
        "invoice",
        "repair_order",
        ["repair_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoice_repair_order_id", "invoice", ["repair_order_id"])
    # Only one active (non-cancelled) invoice per repair order.
    op.execute("""
        CREATE UNIQUE INDEX ux_invoice_repair_order_active
        ON invoice (repair_order_id)
        WHERE repair_order_id IS NOT NULL AND status != 'cancelled'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_invoice_repair_order_active")
    op.drop_index("ix_invoice_repair_order_id", table_name="invoice")
    op.drop_constraint("fk_invoice_repair_order_id", "invoice", type_="foreignkey")

    op.execute("DROP INDEX IF EXISTS ux_dn_repair_order_active")
    op.drop_index("ix_dn_repair_order_id", table_name="delivery_note")
    op.drop_constraint("fk_dn_repair_order_id", "delivery_note", type_="foreignkey")
    op.drop_column("delivery_note", "repair_order_id")
