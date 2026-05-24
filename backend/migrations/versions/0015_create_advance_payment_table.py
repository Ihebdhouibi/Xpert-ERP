"""0008 – create advance_payment table."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advance_payment",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("repair_order_id", sa.BigInteger(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum("cash", "card", "bank_transfer", "cheque", "other", name="payment_method_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_to_invoice_id", sa.BigInteger(), sa.ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_advance_payment_garage_customer", "advance_payment", ["garage_id", "customer_id"])
    op.create_index("ix_advance_payment_invoice", "advance_payment", ["applied_to_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_advance_payment_invoice", table_name="advance_payment")
    op.drop_index("ix_advance_payment_garage_customer", table_name="advance_payment")
    op.drop_table("advance_payment")
