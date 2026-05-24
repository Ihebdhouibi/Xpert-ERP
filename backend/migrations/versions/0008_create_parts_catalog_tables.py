"""M4 - create parts catalog tables (part_category, part, part_equivalent).

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE part_status_enum AS ENUM (
                'active',
                'discontinued',
                'out_of_stock'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # part_category  (self-referential hierarchy)
    # ------------------------------------------------------------------
    op.create_table(
        "part_category",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["part_category.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", "name", "parent_id", name="uq_part_category_garage_name_parent"),
    )
    op.create_index("ix_part_category_garage_id", "part_category", ["garage_id"])
    op.create_index("ix_part_category_parent_id", "part_category", ["parent_id"])

    # ------------------------------------------------------------------
    # part
    # ------------------------------------------------------------------
    op.create_table(
        "part",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("sku_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("unit_of_measure", sa.String(20), nullable=False, server_default="pcs"),
        sa.Column("purchase_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("selling_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("supplier_hint_id", sa.BigInteger(), nullable=True),
        sa.Column("reorder_threshold", sa.Integer(), nullable=True),
        sa.Column("reorder_quantity", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "discontinued", "out_of_stock",
                name="part_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["part_category.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_part_public_id"),
        sa.UniqueConstraint("garage_id", "sku_code", name="uq_part_garage_sku"),
    )
    op.create_index("ix_part_garage_id", "part", ["garage_id"])
    op.create_index("ix_part_garage_sku", "part", ["garage_id", "sku_code"])
    op.create_index("ix_part_garage_category", "part", ["garage_id", "category_id"])
    op.create_index("ix_part_garage_status", "part", ["garage_id", "status"])

    # ------------------------------------------------------------------
    # part_equivalent  (normalised: part_a_id < part_b_id always)
    # ------------------------------------------------------------------
    op.create_table(
        "part_equivalent",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("part_a_id", sa.BigInteger(), nullable=False),
        sa.Column("part_b_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["part_a_id"], ["part.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_b_id"], ["part.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("part_a_id", "part_b_id", name="uq_part_equivalent_pair"),
        sa.CheckConstraint("part_a_id < part_b_id", name="ck_part_equivalent_ordered"),
    )
    op.create_index("ix_part_equivalent_a", "part_equivalent", ["part_a_id"])
    op.create_index("ix_part_equivalent_b", "part_equivalent", ["part_b_id"])


def downgrade() -> None:
    op.drop_table("part_equivalent")
    op.drop_table("part")
    op.drop_table("part_category")
    op.execute("DROP TYPE IF EXISTS part_status_enum")
