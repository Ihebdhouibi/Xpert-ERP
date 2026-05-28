"""0010 – create credit_note and refund tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE credit_note_status_enum AS ENUM ('draft', 'issued', 'void')
    """)

    op.create_table(
        "credit_note",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoice.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("doc_number", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "issued", "void", name="credit_note_status_enum", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("total_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_credit_note_garage_id", "credit_note", ["garage_id"])
    op.create_index("ix_credit_note_invoice_id", "credit_note", ["invoice_id"])
    op.create_index("ix_credit_note_status", "credit_note", ["status"])

    op.create_table(
        "refund",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_id", sa.BigInteger(), sa.ForeignKey("payment.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("credit_note_id", sa.BigInteger(), sa.ForeignKey("credit_note.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "payment_method",
            postgresql.ENUM("cash", "card", "bank_transfer", "cheque", "other", name="payment_method_enum", create_type=False),
            nullable=False,
            server_default="cash",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_refund_garage_id", "refund", ["garage_id"])
    op.create_index("ix_refund_payment_id", "refund", ["payment_id"])
    op.create_index("ix_refund_credit_note_id", "refund", ["credit_note_id"])


def downgrade() -> None:
    op.drop_index("ix_refund_credit_note_id", table_name="refund")
    op.drop_index("ix_refund_payment_id", table_name="refund")
    op.drop_index("ix_refund_garage_id", table_name="refund")
    op.drop_table("refund")

    op.drop_index("ix_credit_note_status", table_name="credit_note")
    op.drop_index("ix_credit_note_invoice_id", table_name="credit_note")
    op.drop_index("ix_credit_note_garage_id", table_name="credit_note")
    op.drop_table("credit_note")

    op.execute("DROP TYPE IF EXISTS credit_note_status_enum")
