"""Add invoice_type column to supplier_invoice

Revision ID: 0061
Revises: 0060
Create Date: 2026-07-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_invoice",
        sa.Column(
            "invoice_type",
            sa.String(20),
            nullable=False,
            server_default="parts",
        ),
    )


def downgrade() -> None:
    op.drop_column("supplier_invoice", "invoice_type")
