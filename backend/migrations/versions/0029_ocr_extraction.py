"""M11 – create ocr_extraction table (Issue #48)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_extraction",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "public_id",
            sa.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", sa.BigInteger, sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False, server_default="paddleocr-3"),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("structured_fields", sa.JSON, nullable=True),
        sa.Column("confidence_scores", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                "needs_review",
                name="ocrextractionstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ocr_extraction_document_id", "ocr_extraction", ["document_id"])
    op.create_index("ix_ocr_extraction_status", "ocr_extraction", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ocr_extraction_status", table_name="ocr_extraction")
    op.drop_index("ix_ocr_extraction_document_id", table_name="ocr_extraction")
    op.drop_table("ocr_extraction")
    op.execute("DROP TYPE IF EXISTS ocrextractionstatus")
