"""M9 – create inspection tables (templates, executions, results, conflict log, vehicle recommendations)."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE inspection_item_status_enum AS ENUM (
                'ok', 'attention', 'defective', 'not_applicable'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE inspection_status_enum AS ENUM (
                'draft', 'in_progress', 'completed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # inspection_template
    # ------------------------------------------------------------------
    op.create_table(
        "inspection_template",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "sections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_inspection_template_public_id"),
    )
    op.create_index("ix_inspection_template_garage", "inspection_template", ["garage_id"])

    # ------------------------------------------------------------------
    # inspection
    # ------------------------------------------------------------------
    op.create_table(
        "inspection",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "repair_order_id",
            sa.BigInteger(),
            sa.ForeignKey("repair_order.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection_template.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mechanic_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "vehicle_id",
            sa.BigInteger(),
            sa.ForeignKey("vehicle.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "in_progress",
                "completed",
                "cancelled",
                name="inspection_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_inspection_public_id"),
    )
    op.create_index("ix_inspection_garage", "inspection", ["garage_id"])
    op.create_index("ix_inspection_garage_status", "inspection", ["garage_id", "status"])
    op.create_index("ix_inspection_repair_order", "inspection", ["repair_order_id"])
    op.create_index("ix_inspection_mechanic", "inspection", ["mechanic_id"])
    op.create_index("ix_inspection_vehicle", "inspection", ["vehicle_id"])

    # ------------------------------------------------------------------
    # inspection_item_result
    # ------------------------------------------------------------------
    op.create_table(
        "inspection_item_result",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "inspection_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_id", sa.String(100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ok",
                "attention",
                "defective",
                "not_applicable",
                name="inspection_item_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "media_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "written_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_id", "item_id", name="uq_inspection_item_result_item"),
    )
    op.create_index(
        "ix_inspection_item_result_inspection", "inspection_item_result", ["inspection_id"]
    )

    # ------------------------------------------------------------------
    # inspection_conflict_log
    # ------------------------------------------------------------------
    op.create_table(
        "inspection_conflict_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "inspection_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_id", sa.String(100), nullable=False),
        sa.Column("client_written_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_written_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discarded_status", sa.String(50), nullable=False),
        sa.Column("kept_status", sa.String(50), nullable=False),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inspection_conflict_log_inspection",
        "inspection_conflict_log",
        ["inspection_id"],
    )

    # ------------------------------------------------------------------
    # vehicle_recommendation
    # ------------------------------------------------------------------
    op.create_table(
        "vehicle_recommendation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "vehicle_id",
            sa.BigInteger(),
            sa.ForeignKey("vehicle.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_inspection_id",
            sa.BigInteger(),
            sa.ForeignKey("inspection.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("item_id", sa.String(100), nullable=False),
        sa.Column("item_label", sa.String(500), nullable=False),
        sa.Column("item_status", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="archived"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_vehicle_recommendation_public_id"),
    )
    op.create_index("ix_vehicle_recommendation_vehicle", "vehicle_recommendation", ["vehicle_id"])
    op.create_index(
        "ix_vehicle_recommendation_garage_vehicle",
        "vehicle_recommendation",
        ["garage_id", "vehicle_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_recommendation_garage_vehicle", table_name="vehicle_recommendation")
    op.drop_index("ix_vehicle_recommendation_vehicle", table_name="vehicle_recommendation")
    op.drop_table("vehicle_recommendation")

    op.drop_index("ix_inspection_conflict_log_inspection", table_name="inspection_conflict_log")
    op.drop_table("inspection_conflict_log")

    op.drop_index("ix_inspection_item_result_inspection", table_name="inspection_item_result")
    op.drop_table("inspection_item_result")

    op.drop_index("ix_inspection_vehicle", table_name="inspection")
    op.drop_index("ix_inspection_mechanic", table_name="inspection")
    op.drop_index("ix_inspection_repair_order", table_name="inspection")
    op.drop_index("ix_inspection_garage_status", table_name="inspection")
    op.drop_index("ix_inspection_garage", table_name="inspection")
    op.drop_table("inspection")

    op.drop_index("ix_inspection_template_garage", table_name="inspection_template")
    op.drop_table("inspection_template")

    op.execute("DROP TYPE IF EXISTS inspection_item_status_enum")
    op.execute("DROP TYPE IF EXISTS inspection_status_enum")
