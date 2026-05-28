"""M8 – create notification_log table."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("template_code", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_notif_garage_id", "notification_log", ["garage_id"])
    op.create_index("ix_notif_garage_status", "notification_log", ["garage_id", "status"])
    op.create_index("ix_notif_recipient_id", "notification_log", ["recipient_id"])


def downgrade() -> None:
    op.drop_index("ix_notif_recipient_id", table_name="notification_log")
    op.drop_index("ix_notif_garage_status", table_name="notification_log")
    op.drop_index("ix_notif_garage_id", table_name="notification_log")
    op.drop_table("notification_log")
