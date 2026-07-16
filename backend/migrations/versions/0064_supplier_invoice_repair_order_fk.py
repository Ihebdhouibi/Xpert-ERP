"""Add repair_order_id FK to supplier_invoice — link a facture service to an OT.

Revision ID: 0064
Revises: 0063
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_invoice",
        sa.Column("repair_order_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_si_repair_order_id",
        "supplier_invoice",
        "repair_order",
        ["repair_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_si_repair_order_id",
        "supplier_invoice",
        ["repair_order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_si_repair_order_id", table_name="supplier_invoice")
    op.drop_constraint("fk_si_repair_order_id", "supplier_invoice", type_="foreignkey")
    op.drop_column("supplier_invoice", "repair_order_id")
