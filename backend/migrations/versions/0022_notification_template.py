"""M8 – create notification_template table."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_template",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False, server_default="'fr'"),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("garage_id", "code", "channel", "locale", name="uq_notif_tmpl"),
    )
    op.create_index(
        "ix_notif_tmpl_garage_code",
        "notification_template",
        ["garage_id", "code", "channel"],
    )


def downgrade() -> None:
    op.drop_index("ix_notif_tmpl_garage_code", table_name="notification_template")
    op.drop_table("notification_template")
