"""M3 - create repair order tables and status event ledger.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enums (idempotent DO blocks)
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE ro_status_enum AS ENUM (
                'created',
                'diagnosis',
                'in_repair',
                'finished',
                'delivered',
                'paused_parts',
                'paused_approval'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # repair_order
    # ------------------------------------------------------------------
    op.create_table(
        "repair_order",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("vehicle_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "created",
                "diagnosis",
                "in_repair",
                "finished",
                "delivered",
                "paused_parts",
                "paused_approval",
                name="ro_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="created",
        ),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("estimated_cost_minor", sa.BigInteger(), nullable=True),
        sa.Column("estimated_cost_currency", sa.String(3), nullable=True),
        sa.Column(
            "actual_cost_minor",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customer.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"], ["vehicle.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_repair_order_public_id"),
    )
    op.create_index("ix_repair_order_garage_id", "repair_order", ["garage_id"])
    op.create_index(
        "ix_repair_order_garage_status", "repair_order", ["garage_id", "status"]
    )
    op.create_index(
        "ix_repair_order_garage_customer", "repair_order", ["garage_id", "customer_id"]
    )
    op.create_index(
        "ix_repair_order_garage_vehicle", "repair_order", ["garage_id", "vehicle_id"]
    )
    op.create_index(
        "ix_repair_order_garage_created", "repair_order", ["garage_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # ro_labor_line (line items for labor)
    # ------------------------------------------------------------------
    op.create_table(
        "ro_labor_line",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ro_id", sa.BigInteger(), nullable=False),
        sa.Column("labor_type", sa.String(100), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("rate_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ro_id"], ["repair_order.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ro_labor_line_ro_id", "ro_labor_line", ["ro_id"])

    # ------------------------------------------------------------------
    # ro_part_line (line items for parts)
    # ------------------------------------------------------------------
    op.create_table(
        "ro_part_line",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ro_id", sa.BigInteger(), nullable=False),
        sa.Column("part_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ro_id"], ["repair_order.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ro_part_line_ro_id", "ro_part_line", ["ro_id"])

    # ------------------------------------------------------------------
    # ro_status_event (append-only status change audit trail)
    # ------------------------------------------------------------------
    op.create_table(
        "ro_status_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ro_id", sa.BigInteger(), nullable=False),
        sa.Column("old_status", sa.String(50), nullable=True),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ro_id"], ["repair_order.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ro_status_event_ro_id", "ro_status_event", ["ro_id"])
    op.create_index(
        "ix_ro_status_event_ro_occurred",
        "ro_status_event",
        ["ro_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("ro_status_event")
    op.drop_table("ro_part_line")
    op.drop_table("ro_labor_line")
    op.drop_table("repair_order")
    op.execute("DROP TYPE IF EXISTS ro_status_enum")
