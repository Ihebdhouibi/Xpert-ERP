"""Create invoice_status_enum and quotation_status_enum native PG types.

Migrations 0012 / 0013 created these columns as VARCHAR + CHECK constraint.
The SQLAlchemy models were later updated to use native Enum types, causing
asyncpg to fail when preparing queries that reference the type by name.

This migration:
1. Creates the two missing PG enum types.
2. Alters the columns to use them (USING cast).
3. Drops the now-redundant CHECK constraints.

Revision ID: 0031
Revises: 0030
"""
from __future__ import annotations

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # invoice_status_enum                                                  #
    # ------------------------------------------------------------------ #
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invoice_status_enum') THEN
                CREATE TYPE invoice_status_enum
                    AS ENUM ('draft', 'issued', 'partial', 'paid', 'cancelled');
            END IF;
        END$$;
        """
    )
    # Drop default, alter column type, restore default
    op.execute("ALTER TABLE invoice ALTER COLUMN status DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE invoice
            ALTER COLUMN status
            TYPE invoice_status_enum
            USING status::invoice_status_enum;
        """
    )
    op.execute("ALTER TABLE invoice ALTER COLUMN status SET DEFAULT 'draft'::invoice_status_enum;")
    # Drop the now-redundant CHECK constraint (ignore if it doesn't exist)
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE invoice DROP CONSTRAINT IF EXISTS ck_invoice_status;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    # ------------------------------------------------------------------ #
    # quotation_status_enum                                                #
    # ------------------------------------------------------------------ #
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'quotation_status_enum') THEN
                CREATE TYPE quotation_status_enum
                    AS ENUM ('draft', 'sent', 'approved', 'rejected', 'expired', 'converted');
            END IF;
        END$$;
        """
    )
    # Drop default, alter column type, restore default
    op.execute("ALTER TABLE quotation ALTER COLUMN status DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE quotation
            ALTER COLUMN status
            TYPE quotation_status_enum
            USING status::quotation_status_enum;
        """
    )
    op.execute("ALTER TABLE quotation ALTER COLUMN status SET DEFAULT 'draft'::quotation_status_enum;")
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE quotation DROP CONSTRAINT IF EXISTS ck_quotation_status;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )


def downgrade() -> None:
    # Revert invoice column back to VARCHAR
    op.execute("ALTER TABLE invoice ALTER COLUMN status DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE invoice
            ALTER COLUMN status
            TYPE VARCHAR(20)
            USING status::VARCHAR;
        """
    )
    op.execute("ALTER TABLE invoice ALTER COLUMN status SET DEFAULT 'draft';")
    op.execute(
        """
        ALTER TABLE invoice
            ADD CONSTRAINT ck_invoice_status
            CHECK (status IN ('draft', 'issued', 'partial', 'paid', 'cancelled'));
        """
    )
    op.execute("DROP TYPE IF EXISTS invoice_status_enum;")

    # Revert quotation column back to VARCHAR
    op.execute("ALTER TABLE quotation ALTER COLUMN status DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE quotation
            ALTER COLUMN status
            TYPE VARCHAR(20)
            USING status::VARCHAR;
        """
    )
    op.execute("ALTER TABLE quotation ALTER COLUMN status SET DEFAULT 'draft';")
    op.execute(
        """
        ALTER TABLE quotation
            ADD CONSTRAINT ck_quotation_status
            CHECK (status IN ('draft', 'sent', 'approved', 'rejected', 'expired', 'converted'));
        """
    )
    op.execute("DROP TYPE IF EXISTS quotation_status_enum;")
