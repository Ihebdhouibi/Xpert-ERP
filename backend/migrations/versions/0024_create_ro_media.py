"""M9 – create ro_media and ro_media_upload_session tables (Issue #42)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ro_media — one row per completed upload
    # ------------------------------------------------------------------
    op.create_table(
        "ro_media",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "inspection_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "ro_id",
            sa.BigInteger(),
            sa.ForeignKey("repair_order.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploader_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Internal S3 key — NEVER returned to clients
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        # Cold-storage archiving
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("archive_storage_key", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_ro_media_public_id"),
    )
    op.create_index("ix_ro_media_garage", "ro_media", ["garage_id"])
    op.create_index("ix_ro_media_inspection", "ro_media", ["inspection_id"])
    op.create_index("ix_ro_media_ro", "ro_media", ["ro_id"])
    op.create_index(
        "ix_ro_media_archive_sweep",
        "ro_media",
        ["archived", "uploaded_at"],
    )

    # ------------------------------------------------------------------
    # ro_media_upload_session — one row per in-flight chunked upload
    # The UUID id doubles as the public session identifier.
    # ------------------------------------------------------------------
    op.create_table(
        "ro_media_upload_session",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "inspection_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "ro_id",
            sa.BigInteger(),
            sa.ForeignKey("repair_order.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploader_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("chunk_size_bytes", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        # [{part_number: int, etag: str}] — grows as chunks land
        sa.Column(
            "received_parts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("s3_upload_id", sa.Text(), nullable=False),
        # pending | complete | aborted
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ro_media_upload_session_garage", "ro_media_upload_session", ["garage_id"]
    )
    op.create_index(
        "ix_ro_media_upload_session_inspection",
        "ro_media_upload_session",
        ["inspection_id"],
    )
    op.create_index(
        "ix_ro_media_upload_session_expires",
        "ro_media_upload_session",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ro_media_upload_session_expires", table_name="ro_media_upload_session")
    op.drop_index(
        "ix_ro_media_upload_session_inspection", table_name="ro_media_upload_session"
    )
    op.drop_index("ix_ro_media_upload_session_garage", table_name="ro_media_upload_session")
    op.drop_table("ro_media_upload_session")

    op.drop_index("ix_ro_media_archive_sweep", table_name="ro_media")
    op.drop_index("ix_ro_media_ro", table_name="ro_media")
    op.drop_index("ix_ro_media_inspection", table_name="ro_media")
    op.drop_index("ix_ro_media_garage", table_name="ro_media")
    op.drop_table("ro_media")
