"""M4 - create stock movement engine tables.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE stock_movement_type AS ENUM (
                'in', 'out', 'adjustment', 'reservation', 'release'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # stock_level  (one row per garage × part, refreshed on each movement)
    # ------------------------------------------------------------------
    op.create_table(
        "stock_level",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("part_id", sa.BigInteger(), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_cost_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", "part_id", name="uq_stock_level_garage_part"),
    )
    op.create_index("ix_stock_level_garage_id", "stock_level", ["garage_id"])
    op.create_index("ix_stock_level_garage_part", "stock_level", ["garage_id", "part_id"])

    # ------------------------------------------------------------------
    # stock_movement  (append-only ledger)
    # ------------------------------------------------------------------
    op.create_table(
        "stock_movement",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("part_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "in", "out", "adjustment", "reservation", "release",
                name="stock_movement_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost_minor", sa.BigInteger(), nullable=True),
        sa.Column("ref_type", sa.String(50), nullable=True),
        sa.Column("ref_id", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("quantity != 0", name="ck_stock_movement_qty_nonzero"),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_movement_garage_part", "stock_movement", ["garage_id", "part_id"])
    op.create_index("ix_stock_movement_garage_created", "stock_movement", ["garage_id", "created_at"])
    op.create_index("ix_stock_movement_ref", "stock_movement", ["ref_type", "ref_id"])

    # ------------------------------------------------------------------
    # low_stock_alert
    # ------------------------------------------------------------------
    op.create_table(
        "low_stock_alert",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("part_id", sa.BigInteger(), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_low_stock_alert_garage", "low_stock_alert", ["garage_id"])
    op.create_index("ix_low_stock_alert_part", "low_stock_alert", ["part_id"])
    op.create_index(
        "ix_low_stock_alert_unack",
        "low_stock_alert",
        ["garage_id", "acknowledged"],
    )


def downgrade() -> None:
    op.drop_table("low_stock_alert")
    op.drop_table("stock_movement")
    op.drop_table("stock_level")
    op.execute("DROP TYPE IF EXISTS stock_movement_type")
