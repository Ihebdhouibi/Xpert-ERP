"""0009 – create cash_session table and add cash_session_id to payment."""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE cash_session_status_enum AS ENUM ('open', 'closed')
    """)
    op.create_table(
        "cash_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="cash_session_status_enum", create_type=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("opened_by_id", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expected_total_cash", sa.BigInteger(), nullable=True),
        sa.Column("counted_total_cash", sa.BigInteger(), nullable=True),
        sa.Column("difference", sa.BigInteger(), nullable=True),
        sa.Column("closing_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_cash_session_garage_status", "cash_session", ["garage_id", "status"])

    # Add cash_session_id to existing payment table
    op.add_column(
        "payment",
        sa.Column(
            "cash_session_id",
            sa.BigInteger(),
            sa.ForeignKey("cash_session.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_payment_cash_session_id", "payment", ["cash_session_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_cash_session_id", table_name="payment")
    op.drop_column("payment", "cash_session_id")
    op.drop_index("ix_cash_session_garage_status", table_name="cash_session")
    op.drop_table("cash_session")
    op.execute("DROP TYPE IF EXISTS cash_session_status_enum")
