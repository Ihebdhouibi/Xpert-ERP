"""0007 – create payment table."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE payment_method_enum AS ENUM (
            'cash', 'card', 'bank_transfer', 'cheque', 'other'
        )
    """)
    op.create_table(
        "payment",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum("cash", "card", "bank_transfer", "cheque", "other", name="payment_method_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_payment_invoice_id", "payment", ["invoice_id"])
    op.create_index("ix_payment_garage_id", "payment", ["garage_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_garage_id", table_name="payment")
    op.drop_index("ix_payment_invoice_id", table_name="payment")
    op.drop_table("payment")
    op.execute("DROP TYPE IF EXISTS payment_method_enum")
