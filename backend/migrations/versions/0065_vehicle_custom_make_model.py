"""0065 — vehicle_custom_make / vehicle_custom_model (user-confirmed dropdown entries)

Revision ID: 0065
Revises: 0064
Create Date: 2026-07-25 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicle_custom_make",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", "name", name="uq_vehicle_custom_make_garage_name"),
    )
    op.create_index("ix_vehicle_custom_make_garage_id", "vehicle_custom_make", ["garage_id"])

    op.create_table(
        "vehicle_custom_model",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("make", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "garage_id", "make", "name", name="uq_vehicle_custom_model_garage_make_name"
        ),
    )
    op.create_index(
        "ix_vehicle_custom_model_garage_make", "vehicle_custom_model", ["garage_id", "make"]
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_custom_model_garage_make", table_name="vehicle_custom_model")
    op.drop_table("vehicle_custom_model")
    op.drop_index("ix_vehicle_custom_make_garage_id", table_name="vehicle_custom_make")
    op.drop_table("vehicle_custom_make")
