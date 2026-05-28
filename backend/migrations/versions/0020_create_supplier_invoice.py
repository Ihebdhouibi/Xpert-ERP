"""M7 – create supplier_invoice table; seed supplier_invoice permissions."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supplier_invoice",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_order.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column(
            "lines",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("total_ht", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_ttc", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("has_discrepancy", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
    )
    op.create_index("uq_si_public_id", "supplier_invoice", ["public_id"], unique=True)
    op.create_index("ix_si_garage_id", "supplier_invoice", ["garage_id"])
    op.create_index("ix_si_garage_status", "supplier_invoice", ["garage_id", "status"])
    op.create_index("ix_si_supplier_id", "supplier_invoice", ["supplier_id"])
    op.create_index("ix_si_po_id", "supplier_invoice", ["purchase_order_id"])

    # ------------------------------------------------------------------
    # Seed permissions
    # ------------------------------------------------------------------
    conn = op.get_bind()
    perms = [
        ("supplier_invoice.read", "supplier_invoice", "read", "View supplier invoices"),
        ("supplier_invoice.create", "supplier_invoice", "create", "Create supplier invoices"),
        ("supplier_invoice.post", "supplier_invoice", "post", "Post and run three-way match"),
        ("supplier_invoice.approve", "supplier_invoice", "approve", "Approve supplier invoices"),
        ("supplier_invoice.override", "supplier_invoice", "override", "Override discrepancies"),
    ]
    for code, resource, action, desc in perms:
        conn.execute(
            sa.text(
                "INSERT INTO permission (code, resource, action, description) "
                "VALUES (:code, :resource, :action, :description) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "resource": resource, "action": action, "description": desc},
        )

    for role_code in ("super_admin", "admin", "inventory_manager"):
        role_row = conn.execute(
            sa.text("SELECT id FROM role WHERE code = :code"),
            {"code": role_code},
        ).fetchone()
        if not role_row:
            continue
        rid = role_row[0]
        for code, *_ in perms:
            p = conn.execute(
                sa.text("SELECT id FROM permission WHERE code = :code"),
                {"code": code},
            ).fetchone()
            if p:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permission (role_id, permission_id) "
                        "VALUES (:rid, :pid) ON CONFLICT DO NOTHING"
                    ),
                    {"rid": rid, "pid": p[0]},
                )


def downgrade() -> None:
    op.drop_index("ix_si_po_id", table_name="supplier_invoice")
    op.drop_index("ix_si_supplier_id", table_name="supplier_invoice")
    op.drop_index("ix_si_garage_status", table_name="supplier_invoice")
    op.drop_index("ix_si_garage_id", table_name="supplier_invoice")
    op.drop_index("uq_si_public_id", table_name="supplier_invoice")
    op.drop_table("supplier_invoice")
