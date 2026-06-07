"""0032 — create delivery_note and delivery_note_line tables

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-06 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_note",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("vehicle_id", sa.BigInteger(), nullable=True),
        sa.Column("invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("doc_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vat_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TND"),
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
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicle.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('draft','issued','delivered','cancelled')",
            name="ck_delivery_note_status",
        ),
    )
    op.create_index("ix_dn_garage_id", "delivery_note", ["garage_id"])
    op.create_index("ix_dn_customer_id", "delivery_note", ["customer_id"])
    op.create_index("ix_dn_status", "delivery_note", ["status"])
    op.create_index("ix_dn_garage_customer", "delivery_note", ["garage_id", "customer_id"])

    op.create_table(
        "delivery_note_line",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("delivery_note_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="part"),
        sa.Column("part_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["delivery_note_id"], ["delivery_note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_dn_line_delivery_note_id", "delivery_note_line", ["delivery_note_id"])


def downgrade() -> None:
    op.drop_index("ix_dn_line_delivery_note_id", table_name="delivery_note_line")
    op.drop_table("delivery_note_line")
    op.drop_index("ix_dn_garage_customer", table_name="delivery_note")
    op.drop_index("ix_dn_status", table_name="delivery_note")
    op.drop_index("ix_dn_customer_id", table_name="delivery_note")
    op.drop_index("ix_dn_garage_id", table_name="delivery_note")
    op.drop_table("delivery_note")
