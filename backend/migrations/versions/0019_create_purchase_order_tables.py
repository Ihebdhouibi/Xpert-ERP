"""M7 – create purchase_order and purchase_order_line tables; seed PO permissions."""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchase_order",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("doc_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_ht", sa.BigInteger(), nullable=False, server_default="0"),
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
    op.create_index("uq_po_public_id", "purchase_order", ["public_id"], unique=True)
    op.create_index("ix_po_garage_id", "purchase_order", ["garage_id"])
    op.create_index("ix_po_garage_status", "purchase_order", ["garage_id", "status"])
    op.create_index("ix_po_supplier_id", "purchase_order", ["supplier_id"])

    op.create_table(
        "purchase_order_line",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "purchase_order_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "part_id",
            sa.BigInteger(),
            sa.ForeignKey("part.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column("unit_price_ht", sa.BigInteger(), nullable=False),
        sa.Column("quantity_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_invoiced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_flag", sa.String(30), nullable=False, server_default="ok"),
    )
    op.create_index("ix_pol_po_id", "purchase_order_line", ["purchase_order_id"])
    op.create_index("ix_pol_part_id", "purchase_order_line", ["part_id"])

    # ------------------------------------------------------------------
    # Seed: purchase_order.read permission (the others exist from 0001)
    # ------------------------------------------------------------------
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO permission (code, resource, action, description) "
            "VALUES (:code, :resource, :action, :description) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {
            "code": "purchase_order.read",
            "resource": "purchase_order",
            "action": "read",
            "description": "View purchase orders",
        },
    )
    # Assign to admin and super_admin (they have ALL permissions)
    result = conn.execute(
        sa.text("SELECT id FROM permission WHERE code = 'purchase_order.read'")
    )
    perm_id = result.scalar()
    if perm_id:
        for role_code in ("super_admin", "admin", "inventory_manager"):
            role_row = conn.execute(
                sa.text("SELECT id FROM role WHERE code = :code"),
                {"code": role_code},
            ).fetchone()
            if role_row:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permission (role_id, permission_id) "
                        "VALUES (:rid, :pid) ON CONFLICT DO NOTHING"
                    ),
                    {"rid": role_row[0], "pid": perm_id},
                )
        # Also assign all PO permissions to inventory_manager
        for perm_code in (
            "purchase_order.create",
            "purchase_order.approve",
            "purchase_order.send",
            "purchase_order.reception.record",
        ):
            p = conn.execute(
                sa.text("SELECT id FROM permission WHERE code = :code"),
                {"code": perm_code},
            ).fetchone()
            if p:
                inv_role = conn.execute(
                    sa.text("SELECT id FROM role WHERE code = 'inventory_manager'")
                ).fetchone()
                if inv_role:
                    conn.execute(
                        sa.text(
                            "INSERT INTO role_permission (role_id, permission_id) "
                            "VALUES (:rid, :pid) ON CONFLICT DO NOTHING"
                        ),
                        {"rid": inv_role[0], "pid": p[0]},
                    )


def downgrade() -> None:
    op.drop_index("ix_pol_part_id", table_name="purchase_order_line")
    op.drop_index("ix_pol_po_id", table_name="purchase_order_line")
    op.drop_table("purchase_order_line")
    op.drop_index("ix_po_supplier_id", table_name="purchase_order")
    op.drop_index("ix_po_garage_status", table_name="purchase_order")
    op.drop_index("ix_po_garage_id", table_name="purchase_order")
    op.drop_index("uq_po_public_id", table_name="purchase_order")
    op.drop_table("purchase_order")
