"""Add source_document_public_id to credit_override_request.

Links each override request to the specific document (BL or invoice) that
triggered it, so an approval for BL-A cannot be reused for BL-B.

Revision ID: 0054
Revises: 0053
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credit_override_request",
        sa.Column("source_document_public_id", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("credit_override_request", "source_document_public_id")
