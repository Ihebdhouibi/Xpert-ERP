"""0036 — bon de retour extras: reversed status, supplier_credit_note.is_exported,
and bon_de_retour.reverse permission.

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-16 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- bon_de_retour: add reversed_at column --------------------------------
    op.add_column(
        "bon_de_retour",
        sa.Column("reversed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Extend the status CHECK constraint to include 'reversed'.
    # PostgreSQL requires DROP + CREATE to alter a check constraint.
    op.drop_constraint("ck_bdr_status", "bon_de_retour")
    op.create_check_constraint(
        "ck_bdr_status",
        "bon_de_retour",
        "status IN ('draft','confirmed','cancelled','reversed')",
    )

    # --- supplier_credit_note: add is_exported flag ---------------------------
    op.add_column(
        "supplier_credit_note",
        sa.Column(
            "is_exported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # --- New permission: bon_de_retour.reverse --------------------------------
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO permission (code, description, resource, action) "
            "VALUES ('bon_de_retour.reverse', "
            "        'Reverse a confirmed bon de retour (undo stock movements)', "
            "        'bon_de_retour', 'reverse') "
            "ON CONFLICT (code) DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r, permission p
            WHERE r.code IN ('super_admin', 'admin', 'inventory_manager')
              AND p.code = 'bon_de_retour.reverse'
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove permission assignments and the permission itself
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE permission_id = "
            "(SELECT id FROM permission WHERE code = 'bon_de_retour.reverse')"
        )
    )
    conn.execute(
        sa.text("DELETE FROM permission WHERE code = 'bon_de_retour.reverse'")
    )

    # Remove is_exported from supplier_credit_note
    op.drop_column("supplier_credit_note", "is_exported")

    # Restore original CHECK constraint (without 'reversed')
    op.drop_constraint("ck_bdr_status", "bon_de_retour")
    op.create_check_constraint(
        "ck_bdr_status",
        "bon_de_retour",
        "status IN ('draft','confirmed','cancelled')",
    )

    # Remove reversed_at column
    op.drop_column("bon_de_retour", "reversed_at")
