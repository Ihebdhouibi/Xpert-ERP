"""M10 – create kpi_snapshot table (Issue #44)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kpi_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("kpi_code", sa.String(80), nullable=False),
        sa.Column("value", sa.Numeric(precision=24, scale=4), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("NULL"),
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "garage_id", "snapshot_date", "kpi_code",
            name="uq_kpi_snapshot_garage_date_code",
        ),
    )

    op.create_index(
        "ix_kpi_snapshot_garage_code_date",
        "kpi_snapshot",
        ["garage_id", "kpi_code", "snapshot_date"],
    )
    op.create_index(
        "ix_kpi_snapshot_garage_date",
        "kpi_snapshot",
        ["garage_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_kpi_snapshot_garage_date", table_name="kpi_snapshot")
    op.drop_index("ix_kpi_snapshot_garage_code_date", table_name="kpi_snapshot")
    op.drop_table("kpi_snapshot")
