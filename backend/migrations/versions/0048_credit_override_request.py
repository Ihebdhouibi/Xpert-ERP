"""Add credit override request table and last_notified_threshold to customer.

Also seeds the credit.override.manage permission.

Revision ID: 0048
Revises: 0047
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add last_notified_threshold to customer
    op.add_column(
        "customer",
        sa.Column("last_notified_threshold", sa.Integer(), nullable=True),
    )

    # 2. Create enum type — use PL/pgSQL block so it is idempotent
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE override_status_enum AS ENUM ('pending', 'approved', 'rejected');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # 3. Create table via raw SQL to avoid SQLAlchemy re-emitting CREATE TYPE
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_override_request (
            id          BIGSERIAL PRIMARY KEY,
            garage_id   BIGINT NOT NULL,
            customer_id BIGINT NOT NULL
                            REFERENCES customer(id) ON DELETE CASCADE,
            requested_by_id BIGINT NOT NULL
                            REFERENCES app_user(id) ON DELETE CASCADE,
            doc_type    VARCHAR(30) NOT NULL,
            status      override_status_enum NOT NULL DEFAULT 'pending',
            approved_by_id BIGINT
                            REFERENCES app_user(id) ON DELETE SET NULL,
            expires_at  TIMESTAMPTZ,
            rejection_reason TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_credit_override_garage_customer
            ON credit_override_request (garage_id, customer_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_credit_override_garage_status
            ON credit_override_request (garage_id, status)
        """
    )

    # 4. Seed credit.override.manage permission
    op.execute(
        """
        INSERT INTO permission (code, resource, action, description)
        VALUES (
            'credit.override.manage',
            'credit',
            'override.manage',
            'Approuver ou refuser les demandes de dérogation de limite de crédit'
        )
        ON CONFLICT (code) DO NOTHING
        """
    )

    # 5. Grant to admin role if it exists
    op.execute(
        """
        INSERT INTO role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM role r
        CROSS JOIN permission p
        WHERE r.code = 'admin'
          AND p.code = 'credit.override.manage'
          AND NOT EXISTS (
              SELECT 1 FROM role_permission rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_credit_override_garage_status")
    op.execute("DROP INDEX IF EXISTS ix_credit_override_garage_customer")
    op.execute("DROP TABLE IF EXISTS credit_override_request")
    op.execute("DROP TYPE IF EXISTS override_status_enum")
    op.drop_column("customer", "last_notified_threshold")
    op.execute("DELETE FROM permission WHERE code = 'credit.override.manage'")
