"""0004 — create document_sequence table

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_sequence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("doc_type", sa.String(10), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("last_number", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", "doc_type", "year", name="uq_sequence_garage_type_year"),
    )
    op.create_index("ix_document_sequence_garage_id", "document_sequence", ["garage_id"])


def downgrade() -> None:
    op.drop_index("ix_document_sequence_garage_id", table_name="document_sequence")
    op.drop_table("document_sequence")
