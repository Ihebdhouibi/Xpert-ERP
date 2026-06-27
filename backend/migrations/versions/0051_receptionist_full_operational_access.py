"""Grant full operational access to the receptionist role.

Same logic as 0050 (secretary) but targeting the `receptionist` role code,
which is the role displayed in the frontend as "Réceptionniste".

Copies every permission admin holds, minus admin-only ones.

Excluded (admin-only):
  system.*                    — garage settings, backup
  audit.read                  — audit log
  users.*                     — user management
  roles.*                     — role management
  admin.sequence.read         — document sequence admin
  config.*                    — runtime config
  credit.override.manage      — approve/reject credit override requests
  customer.credit_limit.update — set client credit limits
  invoice.credit_limit.override — force-bypass without request
  customer.merge              — merge duplicate clients

Revision ID: 0051
Revises: 0050
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
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
    excluded_list = ", ".join(f"'{c}'" for c in _EXCLUDED)

    conn.execute(
        sa.text(
            f"""
            INSERT INTO role_permission (role_id, permission_id)
            SELECT
                (SELECT id FROM role WHERE code = 'receptionist'),
                rp.permission_id
            FROM role r
            JOIN role_permission rp ON rp.role_id = r.id
            JOIN permission p ON p.id = rp.permission_id
            WHERE r.code = 'admin'
              AND p.code NOT IN ({excluded_list})
              AND (SELECT id FROM role WHERE code = 'receptionist') IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM role_permission existing
                  WHERE existing.role_id = (SELECT id FROM role WHERE code = 'receptionist')
                    AND existing.permission_id = rp.permission_id
              )
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    excluded_list = ", ".join(f"'{c}'" for c in _EXCLUDED)

    conn.execute(
        sa.text(
            f"""
            DELETE FROM role_permission
            WHERE role_id = (SELECT id FROM role WHERE code = 'receptionist')
              AND permission_id IN (
                  SELECT rp.permission_id
                  FROM role r
                  JOIN role_permission rp ON rp.role_id = r.id
                  JOIN permission p ON p.id = rp.permission_id
                  WHERE r.code = 'admin'
                    AND p.code NOT IN ({excluded_list})
              )
            """
        )
    )
