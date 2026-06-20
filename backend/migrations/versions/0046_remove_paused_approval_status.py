"""Remove paused_approval from ro_status_enum.

The approval-waiting step is removed from the repair order workflow.
Diagnosis now transitions directly to in_repair.

Any existing rows in paused_approval are rolled back to diagnosis so the
enum value can be safely dropped.

Revision ID: 0046
Revises: 0045
"""
from __future__ import annotations

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Move any live paused_approval orders back to diagnosis before dropping
    # the enum value — PostgreSQL forbids removing a value that is in use.
    op.execute(
        "UPDATE repair_order SET status = 'diagnosis' WHERE status = 'paused_approval'"
    )

    # PostgreSQL does not support ALTER TYPE ... DROP VALUE, so we rebuild the
    # enum: rename → recreate without the value → cast column → drop old type.
    op.execute("ALTER TYPE ro_status_enum RENAME TO ro_status_enum_old")
    op.execute(
        """
        CREATE TYPE ro_status_enum AS ENUM (
            'created',
            'diagnosis',
            'in_repair',
            'finished',
            'delivered',
            'paused_parts'
        )
        """
    )
    op.execute("ALTER TABLE repair_order ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE repair_order
            ALTER COLUMN status TYPE ro_status_enum
            USING status::text::ro_status_enum
        """
    )
    op.execute("ALTER TABLE repair_order ALTER COLUMN status SET DEFAULT 'created'")
    op.execute("DROP TYPE ro_status_enum_old")


def downgrade() -> None:
    op.execute("ALTER TYPE ro_status_enum RENAME TO ro_status_enum_old")
    op.execute(
        """
        CREATE TYPE ro_status_enum AS ENUM (
            'created',
            'diagnosis',
            'in_repair',
            'finished',
            'delivered',
            'paused_parts',
            'paused_approval'
        )
        """
    )
    op.execute("ALTER TABLE repair_order ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE repair_order
            ALTER COLUMN status TYPE ro_status_enum
            USING status::text::ro_status_enum
        """
    )
    op.execute("ALTER TABLE repair_order ALTER COLUMN status SET DEFAULT 'created'")
    op.execute("DROP TYPE ro_status_enum_old")
