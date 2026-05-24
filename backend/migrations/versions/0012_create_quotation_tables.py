"""0005 — create quotation and quotation_line tables

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("vehicle_id", sa.BigInteger(), nullable=True),
        sa.Column("repair_order_id", sa.BigInteger(), nullable=True),
        sa.Column("doc_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vat_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicle.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('draft','sent','approved','rejected','expired','converted')",
            name="ck_quotation_status",
        ),
    )
    op.create_index("ix_quotation_garage_id", "quotation", ["garage_id"])
    op.create_index("ix_quotation_customer_id", "quotation", ["customer_id"])
    op.create_index("ix_quotation_status", "quotation", ["status"])

    op.create_table(
        "quotation_line",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("quotation_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="service"),
        sa.Column("part_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotation.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_quotation_line_quotation_id", "quotation_line", ["quotation_id"])

    # updated_at trigger (PostgreSQL only)
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_quotation_updated_at
        BEFORE UPDATE ON quotation
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_quotation_updated_at ON quotation")
    op.drop_index("ix_quotation_line_quotation_id", table_name="quotation_line")
    op.drop_table("quotation_line")
    op.drop_index("ix_quotation_status", table_name="quotation")
    op.drop_index("ix_quotation_customer_id", table_name="quotation")
    op.drop_index("ix_quotation_garage_id", table_name="quotation")
    op.drop_table("quotation")
