"""M12 – create garage_setting table for runtime-tunable CFG_* values (Issue #54)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "garage_setting",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("garage_id", "key", name="uq_garage_setting_garage_key"),
    )
    op.create_index("ix_garage_setting_garage_id", "garage_setting", ["garage_id"])
    op.create_index("ix_garage_setting_key", "garage_setting", ["key"])

    op.execute(
        sa.text(
            """
            INSERT INTO permission (code, resource, action, description)
            VALUES
              ('config.read',  'config', 'read',  'View runtime CFG_* settings'),
              ('config.write', 'config', 'write', 'Create or update runtime CFG_* settings')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_garage_setting_key", table_name="garage_setting")
    op.drop_index("ix_garage_setting_garage_id", table_name="garage_setting")
    op.drop_table("garage_setting")
    op.execute(
        sa.text(
            "DELETE FROM permission WHERE code IN ('config.read', 'config.write')"
        )
    )
