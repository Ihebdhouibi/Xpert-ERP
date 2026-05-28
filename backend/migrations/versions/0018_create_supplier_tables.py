"""M7 - Supplier entity and supplier_part_price price-history tables.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-28
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # supplier
    # ------------------------------------------------------------------
    op.create_table(
        "supplier",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=True),
        sa.Column("average_delivery_days", sa.Integer(), nullable=True),
        sa.Column("reliability_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_supplier_public_id", "supplier", ["public_id"])
    op.create_index("ix_supplier_garage_id", "supplier", ["garage_id"])
    op.create_index("ix_supplier_garage_status", "supplier", ["garage_id", "status"])

    # ------------------------------------------------------------------
    # supplier_part_price
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_part_price",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "part_id",
            sa.BigInteger(),
            sa.ForeignKey("part.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MAD"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_spp_supplier_id", "supplier_part_price", ["supplier_id"])
    op.create_index("ix_spp_part_id", "supplier_part_price", ["part_id"])
    op.create_index(
        "ix_spp_supplier_part", "supplier_part_price", ["supplier_id", "part_id"]
    )
    op.create_index(
        "ix_spp_part_effective",
        "supplier_part_price",
        ["part_id", "effective_from"],
    )


def downgrade() -> None:
    op.drop_index("ix_spp_part_effective", table_name="supplier_part_price")
    op.drop_index("ix_spp_supplier_part", table_name="supplier_part_price")
    op.drop_index("ix_spp_part_id", table_name="supplier_part_price")
    op.drop_index("ix_spp_supplier_id", table_name="supplier_part_price")
    op.drop_table("supplier_part_price")

    op.drop_index("ix_supplier_garage_status", table_name="supplier")
    op.drop_index("ix_supplier_garage_id", table_name="supplier")
    op.drop_constraint("uq_supplier_public_id", "supplier", type_="unique")
    op.drop_table("supplier")
