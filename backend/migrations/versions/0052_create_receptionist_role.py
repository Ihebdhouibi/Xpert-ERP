"""Create the receptionist role and grant full operational access.

The frontend hardcodes role code 'receptionist' for 'Réceptionniste', but the
DB only had 'secretary'. This migration creates the missing role and grants it
all admin permissions minus the administration-only and credit-override ones.

Migration 0051 tried to grant permissions to 'receptionist' but inserted 0 rows
because the role did not exist yet — this migration fixes that.

Revision ID: 0052
Revises: 0051
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

_EXCLUDED = (
    "system.settings.read",
    "system.settings.update",
    "system.backup.manage",
    "audit.read",
    "users.read",
    "users.create",
    "users.update",
    "users.deactivate",
    "roles.read",
    "roles.assign",
    "roles.manage",
    "admin.sequence.read",
    "config.read",
    "config.write",
    "credit.override.manage",
    "customer.credit_limit.update",
    "invoice.credit_limit.override",
    "customer.merge",
)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create the receptionist role if it doesn't exist
    conn.execute(sa.text("""
        INSERT INTO role (code, display_name, is_system, garage_id)
        SELECT 'receptionist', 'Réceptionniste', true, NULL
        WHERE NOT EXISTS (SELECT 1 FROM role WHERE code = 'receptionist')
    """))

    # 2. Copy all admin permissions minus excluded ones
    excluded_list = ", ".join(f"'{c}'" for c in _EXCLUDED)
    conn.execute(sa.text(f"""
        INSERT INTO role_permission (role_id, permission_id)
        SELECT
            (SELECT id FROM role WHERE code = 'receptionist'),
            rp.permission_id
        FROM role r
        JOIN role_permission rp ON rp.role_id = r.id
        JOIN permission p ON p.id = rp.permission_id
        WHERE r.code = 'admin'
          AND p.code NOT IN ({excluded_list})
          AND NOT EXISTS (
              SELECT 1 FROM role_permission existing
              WHERE existing.role_id = (SELECT id FROM role WHERE code = 'receptionist')
                AND existing.permission_id = rp.permission_id
          )
    """))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        DELETE FROM role_permission
        WHERE role_id = (SELECT id FROM role WHERE code = 'receptionist')
    """))
    conn.execute(sa.text("DELETE FROM role WHERE code = 'receptionist'"))
