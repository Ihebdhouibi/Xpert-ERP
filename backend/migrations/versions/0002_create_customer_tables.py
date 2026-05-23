"""M2 - create customer, customer_contact, customer_balance_event tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0002b"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    # pg_trgm powers fast partial-match search on customer names.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # Enums (DO blocks are idempotent and portable across PG versions —
    # `CREATE TYPE` does not support `IF NOT EXISTS` in any PG release).
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE customer_type_enum AS ENUM ('individual', 'company');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE customer_status_enum AS ENUM ('active', 'inactive', 'blocked');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE customer_contact_channel_enum AS ENUM ('phone', 'email', 'whatsapp');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # customer
    # ------------------------------------------------------------------
    op.create_table(
        "customer",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "individual", "company", name="customer_type_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("fiscal_id", sa.String(50), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("phone_e164", sa.String(20), nullable=True),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("segment", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "inactive",
                "blocked",
                name="customer_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "credit_limit_minor",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("credit_currency", sa.String(3), nullable=True),
        sa.Column(
            "outstanding_minor",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "loyalty_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "type <> 'company' OR company_name IS NOT NULL",
            name="ck_customer_company_has_name",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_customer_public_id"),
    )
    op.create_index("ix_customer_garage_id", "customer", ["garage_id"])
    op.create_index(
        "ix_customer_garage_status", "customer", ["garage_id", "status"]
    )
    op.create_index(
        "ix_customer_garage_phone", "customer", ["garage_id", "phone_e164"]
    )
    op.create_index(
        "ix_customer_garage_email", "customer", ["garage_id", "email"]
    )

    # Partial unique index: fiscal_id is unique per garage among live rows
    # (NULL fiscal_id and soft-deleted rows are exempt).
    op.execute(
        "CREATE UNIQUE INDEX uq_customer_garage_fiscal_id "
        "ON customer (garage_id, fiscal_id) "
        "WHERE fiscal_id IS NOT NULL AND deleted_at IS NULL"
    )

    # Trigram GIN index for fast partial-match search on names.
    op.execute(
        "CREATE INDEX ix_customer_name_trgm "
        "ON customer USING GIN ("
        "full_name gin_trgm_ops, "
        "COALESCE(company_name, '') gin_trgm_ops)"
    )

    # ------------------------------------------------------------------
    # customer_contact
    # ------------------------------------------------------------------
    op.create_table(
        "customer_contact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "channel",
            postgresql.ENUM(
                "phone",
                "email",
                "whatsapp",
                name="customer_contact_channel_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customer.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "channel", "value", name="uq_customer_contact_unique"
        ),
    )
    op.create_index(
        "ix_customer_contact_customer_id", "customer_contact", ["customer_id"]
    )

    # ------------------------------------------------------------------
    # customer_balance_event (append-only ledger)
    # ------------------------------------------------------------------
    op.create_table(
        "customer_balance_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("delta_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("ref_type", sa.String(50), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customer.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_balance_event_customer_id",
        "customer_balance_event",
        ["customer_id"],
    )
    op.create_index(
        "ix_customer_balance_event_customer_occurred",
        "customer_balance_event",
        ["customer_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("customer_balance_event")
    op.drop_table("customer_contact")
    op.execute("DROP INDEX IF EXISTS ix_customer_name_trgm")
    op.execute("DROP INDEX IF EXISTS uq_customer_garage_fiscal_id")
    op.drop_table("customer")
    op.execute("DROP TYPE IF EXISTS customer_contact_channel_enum")
    op.execute("DROP TYPE IF EXISTS customer_status_enum")
    op.execute("DROP TYPE IF EXISTS customer_type_enum")
    # pg_trgm extension is left in place — other modules may depend on it.
