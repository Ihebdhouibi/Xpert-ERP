"""0068 — link advance_payment and refund to the cash session they belong to.

Adds a nullable cash_session_id FK to both tables so cash movements can be
attributed to a session by an explicit link (mirroring payment.cash_session_id)
instead of only by time window. Existing rows keep NULL and continue to be
matched by the session's time window.

Revision ID: 0068
Revises: 0067
Create Date: 2026-07-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE advance_payment
            ADD COLUMN IF NOT EXISTS cash_session_id BIGINT;
        """
    )
    op.execute(
        """
        ALTER TABLE refund
            ADD COLUMN IF NOT EXISTS cash_session_id BIGINT;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE advance_payment
                ADD CONSTRAINT fk_advance_payment_cash_session
                FOREIGN KEY (cash_session_id) REFERENCES cash_session (id)
                ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE refund
                ADD CONSTRAINT fk_refund_cash_session
                FOREIGN KEY (cash_session_id) REFERENCES cash_session (id)
                ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_advance_payment_cash_session "
        "ON advance_payment (cash_session_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_refund_cash_session "
        "ON refund (cash_session_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_refund_cash_session")
    op.execute("DROP INDEX IF EXISTS ix_advance_payment_cash_session")
    op.execute(
        "ALTER TABLE refund DROP CONSTRAINT IF EXISTS fk_refund_cash_session"
    )
    op.execute(
        "ALTER TABLE advance_payment DROP CONSTRAINT IF EXISTS fk_advance_payment_cash_session"
    )
    op.execute("ALTER TABLE refund DROP COLUMN IF EXISTS cash_session_id")
    op.execute("ALTER TABLE advance_payment DROP COLUMN IF EXISTS cash_session_id")
