"""Add supplier_invoice_id FK to supplier_delivery_note

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_delivery_note",
        sa.Column("supplier_invoice_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sdn_supplier_invoice_id",
        "supplier_delivery_note",
        "supplier_invoice",
        ["supplier_invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_sdn_supplier_invoice_id",
        "supplier_delivery_note",
        ["supplier_invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sdn_supplier_invoice_id", table_name="supplier_delivery_note")
    op.drop_constraint("fk_sdn_supplier_invoice_id", "supplier_delivery_note", type_="foreignkey")
    op.drop_column("supplier_delivery_note", "supplier_invoice_id")
