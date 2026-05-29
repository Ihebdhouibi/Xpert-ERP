"""M10 – create accounting_export, add is_exported to payment + supplier_invoice (Issue #46)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounting_export",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("format", sa.String(20), nullable=False, server_default="generic_csv"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("file_storage_key", sa.Text(), nullable=True),
        sa.Column("exported_by", sa.BigInteger(), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "record_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    )
    op.create_index("ix_accounting_export_garage_id", "accounting_export", ["garage_id"])
    op.create_index(
        "ix_accounting_export_garage_period",
        "accounting_export",
        ["garage_id", "period_start", "period_end"],
    )

    op.add_column(
        "payment",
        sa.Column(
            "is_exported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "supplier_invoice",
        sa.Column(
            "is_exported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Seed accounting export permissions
    op.execute(
        sa.text(
            """
            INSERT INTO permission (code, resource, action, description)
            VALUES
              ('accounting_export.read',     'accounting_export', 'read',     'View accounting exports'),
              ('accounting_export.create',   'accounting_export', 'create',   'Trigger accounting export'),
              ('accounting_export.download', 'accounting_export', 'download', 'Download accounting export file')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_column("supplier_invoice", "is_exported")
    op.drop_column("payment", "is_exported")
    op.drop_index("ix_accounting_export_garage_period", table_name="accounting_export")
    op.drop_index("ix_accounting_export_garage_id", table_name="accounting_export")
    op.drop_table("accounting_export")
    op.execute(
        sa.text(
            "DELETE FROM permission WHERE code IN "
            "('accounting_export.read','accounting_export.create','accounting_export.download')"
        )
    )
