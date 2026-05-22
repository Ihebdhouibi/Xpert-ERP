"""M1 - create auth and audit tables, seed roles and permissions.

Revision ID: 0001
Revises: 
Create Date: 2026-05-19
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable citext extension (requires superuser once per DB)
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # ------------------------------------------------------------------
    # permission
    # ------------------------------------------------------------------
    op.create_table(
        "permission",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(150), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_permission_code"),
    )

    # ------------------------------------------------------------------
    # role
    # ------------------------------------------------------------------
    op.create_table(
        "role",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", "code", name="uq_role_garage_code"),
    )

    # ------------------------------------------------------------------
    # role_permission
    # ------------------------------------------------------------------
    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permission.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # ------------------------------------------------------------------
    # user_status enum  (raw SQL so it stays inside the transaction)
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE IF NOT EXISTS user_status_enum AS ENUM ('active', 'inactive', 'locked')"
    )

    # ------------------------------------------------------------------
    # app_user
    # ------------------------------------------------------------------
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", "locked", name="user_status_enum", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "failed_login_count",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("password_reset_token_hash", sa.Text(), nullable=True),
        sa.Column(
            "password_reset_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_app_user_public_id"),
        sa.UniqueConstraint(
            "garage_id", "email", name="uq_app_user_garage_email"
        ),
    )
    op.create_index("ix_app_user_garage_id", "app_user", ["garage_id"])
    op.create_index(
        "ix_app_user_garage_status", "app_user", ["garage_id", "status"]
    )

    # ------------------------------------------------------------------
    # user_role
    # ------------------------------------------------------------------
    op.create_table(
        "user_role",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["app_user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["role.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # ------------------------------------------------------------------
    # audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("garage_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("component", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_garage_id", "audit_log", ["garage_id"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_component", "audit_log", ["component"])

    # ------------------------------------------------------------------
    # Seed: permissions
    # ------------------------------------------------------------------
    from app.modules.auth.seed import PERMISSIONS, ROLES, ROLE_PERMISSIONS  # noqa: PLC0415

    conn = op.get_bind()

    # Insert permissions and capture code -> id map
    perm_rows = [
        {"code": p["code"], "description": p["description"], "resource": p["resource"], "action": p["action"]}
        for p in PERMISSIONS
    ]
    conn.execute(
        sa.text(
            "INSERT INTO permission (code, description, resource, action) "
            "VALUES (:code, :description, :resource, :action) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        perm_rows,
    )

    result = conn.execute(sa.text("SELECT id, code FROM permission"))
    perm_id_map: dict[str, int] = {row[1]: row[0] for row in result}

    # ------------------------------------------------------------------
    # Seed: roles (system roles, garage_id = NULL)
    # ------------------------------------------------------------------
    role_rows = [
        {"code": r["code"], "display_name": r["display_name"], "is_system": r["is_system"]}
        for r in ROLES
    ]
    conn.execute(
        sa.text(
            "INSERT INTO role (garage_id, code, display_name, is_system) "
            "VALUES (NULL, :code, :display_name, :is_system) "
            "ON CONFLICT (garage_id, code) DO NOTHING"
        ),
        role_rows,
    )

    result = conn.execute(sa.text("SELECT id, code FROM role WHERE garage_id IS NULL"))
    role_id_map: dict[str, int] = {row[1]: row[0] for row in result}

    # ------------------------------------------------------------------
    # Seed: role_permission assignments
    # ------------------------------------------------------------------
    rp_rows: list[dict[str, int]] = []
    for role_code, perm_codes in ROLE_PERMISSIONS.items():
        role_id = role_id_map.get(role_code)
        if role_id is None:
            continue
        for perm_code in perm_codes:
            perm_id = perm_id_map.get(perm_code)
            if perm_id is None:
                continue
            rp_rows.append({"role_id": role_id, "permission_id": perm_id})

    if rp_rows:
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (role_id, permission_id) "
                "VALUES (:role_id, :permission_id) "
                "ON CONFLICT DO NOTHING"
            ),
            rp_rows,
        )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("user_role")
    op.drop_table("app_user")
    op.drop_table("role_permission")
    op.drop_table("role")
    op.drop_table("permission")
    op.execute("DROP TYPE IF EXISTS user_status_enum")
    op.execute("DROP EXTENSION IF EXISTS citext")
