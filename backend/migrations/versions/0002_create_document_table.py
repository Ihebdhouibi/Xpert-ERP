"""M2 - create document table (GED entry point).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE IF NOT EXISTS document_status_enum AS ENUM ('active', 'deleted')"
    )
    op.execute(
        """
        CREATE TYPE IF NOT EXISTS document_category_enum AS ENUM (
            'registration_card', 'id_doc', 'insurance', 'accident_photo',
            'invoice', 'supplier_invoice', 'repair_attachment', 'generic'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE IF NOT EXISTS owner_entity_type_enum AS ENUM (
            'customer', 'vehicle', 'repair_order',
            'invoice', 'supplier_invoice', 'generic'
        )
        """
    )

    # ------------------------------------------------------------------
    # document
    # ------------------------------------------------------------------
    op.create_table(
        "document",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "owner_entity_type",
            postgresql.ENUM(
                "customer",
                "vehicle",
                "repair_order",
                "invoice",
                "supplier_invoice",
                "generic",
                name="owner_entity_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("owner_entity_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "category",
            postgresql.ENUM(
                "registration_card",
                "id_doc",
                "insurance",
                "accident_photo",
                "invoice",
                "supplier_invoice",
                "repair_attachment",
                "generic",
                name="document_category_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "deleted",
                name="document_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_document_public_id"),
    )

    op.create_index("ix_document_garage_id", "document", ["garage_id"])
    op.create_index(
        "ix_document_garage_owner",
        "document",
        ["garage_id", "owner_entity_type", "owner_entity_id"],
    )
    op.create_index(
        "ix_document_garage_category",
        "document",
        ["garage_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_garage_category", table_name="document")
    op.drop_index("ix_document_garage_owner", table_name="document")
    op.drop_index("ix_document_garage_id", table_name="document")
    op.drop_table("document")

    op.execute("DROP TYPE IF EXISTS document_status_enum")
    op.execute("DROP TYPE IF EXISTS document_category_enum")
    op.execute("DROP TYPE IF EXISTS owner_entity_type_enum")
