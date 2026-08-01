"""Make part SKU uniqueness exclude soft-deleted rows.

Previously uq_part_garage_sku was a plain UNIQUE(garage_id, sku_code)
constraint, but PartRepository.get_by_sku() only checks non-deleted
parts. That mismatch let a soft-deleted part's SKU block recreation
of a new part with the same code, surfacing as a raw IntegrityError
(500) instead of the intended "SKU already exists" error.

Revision ID: 0070
Revises: 0069
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE part DROP CONSTRAINT IF EXISTS uq_part_garage_sku")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_garage_sku
        ON part (garage_id, sku_code)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_part_garage_sku")
    op.execute(
        """
        ALTER TABLE part
        ADD CONSTRAINT uq_part_garage_sku UNIQUE (garage_id, sku_code)
        """
    )
