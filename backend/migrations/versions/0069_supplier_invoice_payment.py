"""0069 — capture payment details on supplier_invoice and link to cash session.

Adds payment_method, paid_amount_minor, paid_at and a nullable cash_session_id
FK to supplier_invoice so that marking an invoice paid records how/when it was
paid, and — for cash payments — is attributed to the open cash session
(mirroring advance_payment/refund.cash_session_id from migration 0068).

Revision ID: 0069
Revises: 0068
Create Date: 2026-07-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE supplier_invoice
            ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20);
        """
    )
    op.execute(
        """
        ALTER TABLE supplier_invoice
            ADD COLUMN IF NOT EXISTS paid_amount_minor BIGINT;
        """
    )
    op.execute(
        """
        ALTER TABLE supplier_invoice
            ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        ALTER TABLE supplier_invoice
            ADD COLUMN IF NOT EXISTS cash_session_id BIGINT;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE supplier_invoice
                ADD CONSTRAINT fk_supplier_invoice_cash_session
                FOREIGN KEY (cash_session_id) REFERENCES cash_session (id)
                ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_supplier_invoice_cash_session "
        "ON supplier_invoice (cash_session_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_supplier_invoice_cash_session")
    op.execute(
        "ALTER TABLE supplier_invoice DROP CONSTRAINT IF EXISTS fk_supplier_invoice_cash_session"
    )
    op.execute("ALTER TABLE supplier_invoice DROP COLUMN IF EXISTS cash_session_id")
    op.execute("ALTER TABLE supplier_invoice DROP COLUMN IF EXISTS paid_at")
    op.execute("ALTER TABLE supplier_invoice DROP COLUMN IF EXISTS paid_amount_minor")
    op.execute("ALTER TABLE supplier_invoice DROP COLUMN IF EXISTS payment_method")
