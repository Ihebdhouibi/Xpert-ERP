"""0066 — credit_limit_change_request table (receptionist-requests / admin-approves
credit limit changes on existing customers).

Revision ID: 0066
Revises: 0065
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create enum type — idempotent
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE credit_limit_request_status_enum AS ENUM ('pending', 'approved', 'rejected');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # 2. Create table via raw SQL to avoid SQLAlchemy re-emitting CREATE TYPE
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_limit_change_request (
            id          BIGSERIAL PRIMARY KEY,
            garage_id   BIGINT NOT NULL,
            customer_id BIGINT NOT NULL
                            REFERENCES customer(id) ON DELETE CASCADE,
            requested_by_id BIGINT NOT NULL
                            REFERENCES app_user(id) ON DELETE CASCADE,
            current_credit_limit_minor BIGINT NOT NULL,
            requested_credit_limit_minor BIGINT NOT NULL,
            requested_credit_currency VARCHAR(3) NOT NULL,
            reason      TEXT NOT NULL,
            status      credit_limit_request_status_enum NOT NULL DEFAULT 'pending',
            approved_by_id BIGINT
                            REFERENCES app_user(id) ON DELETE SET NULL,
            rejection_reason TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_credit_limit_request_garage_customer
            ON credit_limit_change_request (garage_id, customer_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_credit_limit_request_garage_status
            ON credit_limit_change_request (garage_id, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_credit_limit_request_garage_status")
    op.execute("DROP INDEX IF EXISTS ix_credit_limit_request_garage_customer")
    op.execute("DROP TABLE IF EXISTS credit_limit_change_request")
    op.execute("DROP TYPE IF EXISTS credit_limit_request_status_enum")
