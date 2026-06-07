"""0034 — make supplier_invoice.supplier_id / purchase_order_id nullable

Allows standalone supplier invoices created from OCR (no linked purchase order
yet). PO-based 3-way matching still applies when a PO is present.

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-08 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "supplier_invoice", "supplier_id",
        existing_type=sa.BigInteger(), nullable=True,
    )
    op.alter_column(
        "supplier_invoice", "purchase_order_id",
        existing_type=sa.BigInteger(), nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "supplier_invoice", "purchase_order_id",
        existing_type=sa.BigInteger(), nullable=False,
    )
    op.alter_column(
        "supplier_invoice", "supplier_id",
        existing_type=sa.BigInteger(), nullable=False,
    )
