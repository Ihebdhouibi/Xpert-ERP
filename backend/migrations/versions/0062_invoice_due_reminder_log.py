"""Create invoice_due_reminder_log for pre-due admin reminder tier dedup.

Tracks which (invoice, tier_days) pre-due reminder pairs have already been
sent, so the scheduler fires each tier (J-30/J-14/J-7) exactly once per
invoice regardless of how many times the job ticks.

Revision ID: 0062
Revises: 0061
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_due_reminder_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("tier_days", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", "tier_days", name="uq_invoice_due_reminder_log_invoice_tier"),
    )
    op.create_index(
        "ix_invoice_due_reminder_log_invoice_id",
        "invoice_due_reminder_log",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_due_reminder_log_invoice_id", table_name="invoice_due_reminder_log")
    op.drop_table("invoice_due_reminder_log")
