"""M3 - create ro_time_entry and ro_comment tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ro_time_entry
    # ------------------------------------------------------------------
    op.create_table(
        "ro_time_entry",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ro_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ro_id"], ["repair_order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ro_time_entry_ro_id", "ro_time_entry", ["ro_id"])
    op.create_index("ix_ro_time_entry_ro_user", "ro_time_entry", ["ro_id", "user_id"])

    # At most one open (not-yet-ended) entry per user per RO
    op.execute(
        "CREATE UNIQUE INDEX uq_ro_time_entry_open "
        "ON ro_time_entry (ro_id, user_id) "
        "WHERE ended_at IS NULL"
    )

    # ------------------------------------------------------------------
    # ro_comment
    # ------------------------------------------------------------------
    op.create_table(
        "ro_comment",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ro_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["ro_id"], ["repair_order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ro_comment_ro_id", "ro_comment", ["ro_id"])
    op.create_index(
        "ix_ro_comment_ro_created", "ro_comment", ["ro_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("ro_comment")
    op.execute("DROP INDEX IF EXISTS uq_ro_time_entry_open")
    op.drop_table("ro_time_entry")
