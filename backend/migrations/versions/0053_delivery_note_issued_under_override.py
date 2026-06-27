"""Add issued_under_override flag to delivery_note.

When a BL is issued past a customer's credit limit using an admin-approved
override, this flag is set True. The invoice service uses it to skip the
credit check when converting that specific BL to an invoice — the approval
already covers the transaction.

Revision ID: 0053
Revises: 0052
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_note",
        sa.Column(
            "issued_under_override",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("delivery_note", "issued_under_override")
