"""M4 - add assigned_user_id to repair_order, create ro_photo table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # repair_order — mechanic assignment column
    # ------------------------------------------------------------------
    op.add_column(
        "repair_order",
        sa.Column(
            "assigned_user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_repair_order_assigned_user", "repair_order", ["assigned_user_id"]
    )

    # ------------------------------------------------------------------
    # ro_photo
    # ------------------------------------------------------------------
    op.create_table(
        "ro_photo",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ro_id", sa.BigInteger(), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["ro_id"], ["repair_order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ro_photo_ro_id", "ro_photo", ["ro_id"])
    op.create_index("ix_ro_photo_garage_ro", "ro_photo", ["garage_id", "ro_id"])


def downgrade() -> None:
    op.drop_table("ro_photo")
    op.drop_index("ix_repair_order_assigned_user", table_name="repair_order")
    op.drop_column("repair_order", "assigned_user_id")
