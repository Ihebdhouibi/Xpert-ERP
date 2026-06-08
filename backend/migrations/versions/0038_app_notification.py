"""0038 — in-app notifications (bell inbox)

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-09 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_notification",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_notification_garage_id", "app_notification", ["garage_id"])
    op.create_index("ix_app_notification_recipient_id", "app_notification", ["recipient_id"])
    op.create_index("ix_app_notification_recipient", "app_notification", ["recipient_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_app_notification_recipient", table_name="app_notification")
    op.drop_index("ix_app_notification_recipient_id", table_name="app_notification")
    op.drop_index("ix_app_notification_garage_id", table_name="app_notification")
    op.drop_table("app_notification")
