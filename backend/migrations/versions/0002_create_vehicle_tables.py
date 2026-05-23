"""M2 - create vehicle, ownership history and registration alias tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23

NOTE: If you are merging this branch with another branch that also produced a
0002 migration (e.g. the document-upload branch), rename one of them to 0003
and update its down_revision accordingly before running `alembic upgrade head`.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TYPE IF NOT EXISTS fuel_type_enum AS ENUM
        ('gasoline', 'diesel', 'hybrid', 'ev', 'lpg', 'cng')
        """
    )
    op.execute(
        """
        CREATE TYPE IF NOT EXISTS vehicle_status_enum AS ENUM
        ('active', 'inactive', 'scrapped')
        """
    )

    # ------------------------------------------------------------------
    # vehicle
    # ------------------------------------------------------------------
    op.create_table(
        "vehicle",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("registration", sa.String(50), nullable=True),
        sa.Column("vin", sa.String(17), nullable=True),
        sa.Column("make", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column(
            "fuel_type",
            postgresql.ENUM(
                "gasoline", "diesel", "hybrid", "ev", "lpg", "cng",
                name="fuel_type_enum", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("mileage_current", sa.Integer(), nullable=True),
        sa.Column("last_service_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("technical_inspection_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("maintenance_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "inactive", "scrapped",
                name="vehicle_status_enum", create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
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
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", "registration", name="uq_vehicle_garage_registration"),
        sa.UniqueConstraint("garage_id", "vin", name="uq_vehicle_garage_vin"),
    )
    op.create_index("ix_vehicle_garage_id", "vehicle", ["garage_id"])
    op.create_index("ix_vehicle_customer_id", "vehicle", ["customer_id"])

    # Trigger: auto-update updated_at on every row update
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_vehicle_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_vehicle_updated_at
        BEFORE UPDATE ON vehicle
        FOR EACH ROW EXECUTE FUNCTION update_vehicle_updated_at();
        """
    )

    # ------------------------------------------------------------------
    # vehicle_ownership_history
    # ------------------------------------------------------------------
    op.create_table(
        "vehicle_ownership_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("previous_customer_id", sa.BigInteger(), nullable=True),
        sa.Column("new_customer_id", sa.BigInteger(), nullable=True),
        sa.Column("transferred_by", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "transferred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicle.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ownership_history_vehicle_id", "vehicle_ownership_history", ["vehicle_id"])
    op.create_index("ix_ownership_history_garage_id", "vehicle_ownership_history", ["garage_id"])

    # ------------------------------------------------------------------
    # vehicle_registration_alias
    # ------------------------------------------------------------------
    op.create_table(
        "vehicle_registration_alias",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("registration", sa.String(50), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicle.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reg_alias_vehicle_id", "vehicle_registration_alias", ["vehicle_id"])
    op.create_index(
        "ix_reg_alias_garage_registration",
        "vehicle_registration_alias",
        ["garage_id", "registration"],
    )


def downgrade() -> None:
    op.drop_index("ix_reg_alias_garage_registration", table_name="vehicle_registration_alias")
    op.drop_index("ix_reg_alias_vehicle_id", table_name="vehicle_registration_alias")
    op.drop_table("vehicle_registration_alias")

    op.drop_index("ix_ownership_history_garage_id", table_name="vehicle_ownership_history")
    op.drop_index("ix_ownership_history_vehicle_id", table_name="vehicle_ownership_history")
    op.drop_table("vehicle_ownership_history")

    op.execute("DROP TRIGGER IF EXISTS trg_vehicle_updated_at ON vehicle")
    op.execute("DROP FUNCTION IF EXISTS update_vehicle_updated_at()")
    op.drop_index("ix_vehicle_customer_id", table_name="vehicle")
    op.drop_index("ix_vehicle_garage_id", table_name="vehicle")
    op.drop_table("vehicle")

    op.execute("DROP TYPE IF EXISTS vehicle_status_enum")
    op.execute("DROP TYPE IF EXISTS fuel_type_enum")
