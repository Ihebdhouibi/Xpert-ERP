"""0035 — create bon_de_retour, bon_de_retour_line, supplier_credit_note tables
and seed bon_de_retour.* / supplier_credit_note.* permissions.

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-16 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


_NEW_PERMISSIONS = [
    {"code": "bon_de_retour.read", "resource": "bon_de_retour", "action": "read", "description": "View bon de retour"},
    {"code": "bon_de_retour.create", "resource": "bon_de_retour", "action": "create", "description": "Create draft bon de retour"},
    {"code": "bon_de_retour.update", "resource": "bon_de_retour", "action": "update", "description": "Edit a draft bon de retour"},
    {"code": "bon_de_retour.confirm", "resource": "bon_de_retour", "action": "confirm", "description": "Confirm bon de retour (assign number, move stock)"},
    {"code": "bon_de_retour.cancel", "resource": "bon_de_retour", "action": "cancel", "description": "Cancel a draft bon de retour"},
    {"code": "supplier_credit_note.read", "resource": "supplier_credit_note", "action": "read", "description": "View supplier credit notes (avoir fournisseur)"},
    {"code": "supplier_credit_note.create", "resource": "supplier_credit_note", "action": "create", "description": "Create a supplier credit note"},
    {"code": "supplier_credit_note.issue", "resource": "supplier_credit_note", "action": "issue", "description": "Issue a supplier credit note"},
    {"code": "supplier_credit_note.void", "resource": "supplier_credit_note", "action": "void", "description": "Void a supplier credit note"},
]

_TARGET_ROLES = ("super_admin", "admin", "inventory_manager")


def upgrade() -> None:
    # --- bon_de_retour ------------------------------------------------------
    op.create_table(
        "bon_de_retour",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("party_type", sa.String(20), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("supplier_id", sa.BigInteger(), nullable=True),
        sa.Column("source_invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("source_supplier_invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("doc_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vat_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("credit_note_id", sa.BigInteger(), nullable=True),
        sa.Column("supplier_credit_note_id", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_invoice_id"], ["invoice.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_supplier_invoice_id"], ["supplier_invoice.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["credit_note_id"], ["credit_note.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL"),
        # supplier_credit_note_id FK added after that table exists (circular dep)
        sa.CheckConstraint("party_type IN ('client','supplier')", name="ck_bdr_party_type"),
        sa.CheckConstraint("status IN ('draft','confirmed','cancelled')", name="ck_bdr_status"),
    )
    op.create_index("ix_bdr_garage_id", "bon_de_retour", ["garage_id"])
    op.create_index("ix_bdr_status", "bon_de_retour", ["status"])
    op.create_index("ix_bdr_party_type", "bon_de_retour", ["party_type"])
    op.create_index("ix_bdr_customer_id", "bon_de_retour", ["customer_id"])
    op.create_index("ix_bdr_supplier_id", "bon_de_retour", ["supplier_id"])
    op.create_index("ix_bdr_garage_status", "bon_de_retour", ["garage_id", "status"])

    # --- bon_de_retour_line -------------------------------------------------
    op.create_table(
        "bon_de_retour_line",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bon_de_retour_id", sa.BigInteger(), nullable=False),
        sa.Column("part_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("condition", sa.String(20), nullable=True),
        sa.Column("restock", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["bon_de_retour_id"], ["bon_de_retour.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_bdr_line_bon_de_retour_id", "bon_de_retour_line", ["bon_de_retour_id"])

    # --- supplier_credit_note (avoir fournisseur) ---------------------------
    op.create_table(
        "supplier_credit_note",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("bon_de_retour_id", sa.BigInteger(), nullable=True),
        sa.Column("doc_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_ht_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_ttc_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("voided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_invoice_id"], ["supplier_invoice.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bon_de_retour_id"], ["bon_de_retour.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('draft','issued','void')", name="ck_scn_status"),
    )
    op.create_index("ix_scn_garage_id", "supplier_credit_note", ["garage_id"])
    op.create_index("ix_scn_supplier_id", "supplier_credit_note", ["supplier_id"])
    op.create_index("ix_scn_status", "supplier_credit_note", ["status"])
    op.create_index("ix_scn_bon_de_retour_id", "supplier_credit_note", ["bon_de_retour_id"])

    # bon_de_retour.supplier_credit_note_id is intentionally a plain reference column
    # (no FK constraint) to avoid a cycle with supplier_credit_note.bon_de_retour_id.

    # --- Permissions --------------------------------------------------------
    conn = op.get_bind()
    for perm in _NEW_PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permission (code, description, resource, action) "
                "VALUES (:code, :description, :resource, :action) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            perm,
        )
    perm_rows = conn.execute(
        sa.text("SELECT id, code FROM permission WHERE code = ANY(:codes)"),
        {"codes": [p["code"] for p in _NEW_PERMISSIONS]},
    )
    perm_map = {row[1]: row[0] for row in perm_rows}

    role_rows = conn.execute(
        sa.text("SELECT id, code FROM role WHERE code = ANY(:codes)"),
        {"codes": list(_TARGET_ROLES)},
    )
    role_map = {row[1]: row[0] for row in role_rows}

    for role_id in role_map.values():
        for perm_id in perm_map.values():
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_id, "perm_id": perm_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE permission_id IN "
            "(SELECT id FROM permission WHERE code = ANY(:codes))"
        ),
        {"codes": [p["code"] for p in _NEW_PERMISSIONS]},
    )
    conn.execute(
        sa.text("DELETE FROM permission WHERE code = ANY(:codes)"),
        {"codes": [p["code"] for p in _NEW_PERMISSIONS]},
    )

    op.drop_index("ix_scn_bon_de_retour_id", table_name="supplier_credit_note")
    op.drop_index("ix_scn_status", table_name="supplier_credit_note")
    op.drop_index("ix_scn_supplier_id", table_name="supplier_credit_note")
    op.drop_index("ix_scn_garage_id", table_name="supplier_credit_note")
    op.drop_table("supplier_credit_note")

    op.drop_index("ix_bdr_line_bon_de_retour_id", table_name="bon_de_retour_line")
    op.drop_table("bon_de_retour_line")

    op.drop_index("ix_bdr_garage_status", table_name="bon_de_retour")
    op.drop_index("ix_bdr_supplier_id", table_name="bon_de_retour")
    op.drop_index("ix_bdr_customer_id", table_name="bon_de_retour")
    op.drop_index("ix_bdr_party_type", table_name="bon_de_retour")
    op.drop_index("ix_bdr_status", table_name="bon_de_retour")
    op.drop_index("ix_bdr_garage_id", table_name="bon_de_retour")
    op.drop_table("bon_de_retour")
