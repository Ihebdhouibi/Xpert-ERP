"""M11 – add extracted_text, archived columns to document; GIN FTS index (Issue #47)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # New columns on the existing document table
    # ------------------------------------------------------------------
    op.add_column(
        "document",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "document",
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "document",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # GIN index for French full-text search over filename + extracted_text
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX ix_document_fts
        ON document
        USING GIN (
            to_tsvector(
                'french',
                coalesce(filename, '') || ' ' || coalesce(extracted_text, '')
            )
        )
        """
    )

    # ------------------------------------------------------------------
    # Index for archive-sweep queries (find old non-archived active docs)
    # ------------------------------------------------------------------
    op.create_index(
        "ix_document_archive_sweep",
        "document",
        ["garage_id", "archived", "uploaded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_archive_sweep", table_name="document")
    op.execute("DROP INDEX IF EXISTS ix_document_fts")
    op.drop_column("document", "archived_at")
    op.drop_column("document", "archived")
    op.drop_column("document", "extracted_text")
