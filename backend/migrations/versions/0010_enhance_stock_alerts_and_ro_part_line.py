"""M4 - enhance low_stock_alert (status enum) and add part_id to ro_part_line.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # low_stock_alert: replace boolean `acknowledged` with status enum
    # and add suggested supplier / reorder quantity fields
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE low_stock_alert_status AS ENUM ('open', 'acknowledged', 'resolved');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # Add new status column (nullable first so we can backfill)
    op.add_column(
        "low_stock_alert",
        sa.Column(
            "status",
            postgresql.ENUM(
                "open", "acknowledged", "resolved",
                name="low_stock_alert_status",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # Backfill status from old acknowledged boolean
    op.execute(
        "UPDATE low_stock_alert SET status = 'acknowledged' WHERE acknowledged = TRUE"
    )
    op.execute(
        "UPDATE low_stock_alert SET status = 'open' WHERE acknowledged = FALSE OR acknowledged IS NULL"
    )

    # Make status non-nullable
    op.alter_column("low_stock_alert", "status", nullable=False)

    # Add suggested fields (nullable)
    op.add_column(
        "low_stock_alert",
        sa.Column("suggested_supplier_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "low_stock_alert",
        sa.Column("suggested_reorder_quantity", sa.Integer(), nullable=True),
    )

    # Drop old acknowledged column and its index
    op.drop_index("ix_low_stock_alert_unack", table_name="low_stock_alert")
    op.drop_column("low_stock_alert", "acknowledged")

    # New index on status for efficient filtering
    op.create_index(
        "ix_low_stock_alert_status",
        "low_stock_alert",
        ["garage_id", "status"],
    )

    # ------------------------------------------------------------------
    # ro_part_line: add optional FK to catalog part
    # ------------------------------------------------------------------
    op.add_column(
        "ro_part_line",
        sa.Column("part_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ro_part_line_part_id",
        "ro_part_line",
        "part",
        ["part_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ro_part_line_part_id", "ro_part_line", ["part_id"])


def downgrade() -> None:
    op.drop_index("ix_ro_part_line_part_id", table_name="ro_part_line")
    op.drop_constraint("fk_ro_part_line_part_id", "ro_part_line", type_="foreignkey")
    op.drop_column("ro_part_line", "part_id")

    op.drop_index("ix_low_stock_alert_status", table_name="low_stock_alert")
    op.add_column(
        "low_stock_alert",
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.execute(
        "UPDATE low_stock_alert SET acknowledged = TRUE WHERE status = 'acknowledged'"
    )
    op.create_index(
        "ix_low_stock_alert_unack",
        "low_stock_alert",
        ["garage_id", "acknowledged"],
    )
    op.drop_column("low_stock_alert", "suggested_reorder_quantity")
    op.drop_column("low_stock_alert", "suggested_supplier_id")
    op.drop_column("low_stock_alert", "status")
    op.execute("DROP TYPE IF EXISTS low_stock_alert_status")
