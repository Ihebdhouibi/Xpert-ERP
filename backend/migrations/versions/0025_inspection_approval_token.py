"""M9 – create inspection_approval_token table (Issue #43)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inspection_approval_token",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(36), nullable=False),
        sa.Column("inspection_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspection.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_inspection_approval_token_jti"),
    )
    op.create_index(
        "ix_inspection_approval_token_jti",
        "inspection_approval_token",
        ["jti"],
    )
    op.create_index(
        "ix_inspection_approval_token_inspection",
        "inspection_approval_token",
        ["inspection_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inspection_approval_token_inspection",
        table_name="inspection_approval_token",
    )
    op.drop_index(
        "ix_inspection_approval_token_jti",
        table_name="inspection_approval_token",
    )
    op.drop_table("inspection_approval_token")
