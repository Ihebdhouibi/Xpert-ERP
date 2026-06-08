"""0035 — make invoice.customer_id nullable (OCR-captured draft invoices)

Allows draft customer invoices created from OCR before a customer is linked.

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-08 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "invoice", "customer_id",
        existing_type=sa.BigInteger(), nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "invoice", "customer_id",
        existing_type=sa.BigInteger(), nullable=False,
    )
