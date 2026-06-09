"""0039 — seed/assign permissions that routers required but no role held

Several routers guarded endpoints with permission codes that were never
granted to any role (or never created at all), so every request returned
403 — even for admin:

  * supplier.delete        — never existed; DELETE /suppliers was guarded
                             by the non-existent `supplier.write`
  * admin.sequence.read    — never existed; GET /sequences was guarded by it
  * config.read / .write   — created by migration 0030 but never assigned

This migration creates the missing permissions and assigns the full set to
the appropriate roles, bringing existing databases in line with the seed
catalog (app.modules.auth.seed) used for fresh installs.

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-09 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

# Permissions to ensure exist (idempotent — config.* already created by 0030)
_PERMISSIONS = [
    {"code": "supplier.delete", "resource": "supplier", "action": "delete",
     "description": "Delete supplier"},
    {"code": "admin.sequence.read", "resource": "admin", "action": "sequence.read",
     "description": "View document sequence counters"},
    {"code": "config.read", "resource": "config", "action": "read",
     "description": "View runtime CFG_* settings"},
    {"code": "config.write", "resource": "config", "action": "write",
     "description": "Create or update runtime CFG_* settings"},
]

# role code -> permission codes to grant
_GRANTS: dict[str, list[str]] = {
    "super_admin": ["supplier.delete", "admin.sequence.read", "config.read", "config.write"],
    "admin": ["supplier.delete", "admin.sequence.read", "config.read", "config.write"],
    "inventory_manager": ["supplier.delete"],
    "accountant": ["admin.sequence.read"],
}


def upgrade() -> None:
    conn = op.get_bind()

    for perm in _PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permission (code, description, resource, action) "
                "VALUES (:code, :description, :resource, :action) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            perm,
        )

    for role_code, perm_codes in _GRANTS.items():
        for perm_code in perm_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "SELECT r.id, p.id FROM role r, permission p "
                    "WHERE r.code = :role_code AND p.code = :perm_code "
                    "ON CONFLICT DO NOTHING"
                ),
                {"role_code": role_code, "perm_code": perm_code},
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove the role grants and the two permissions this migration introduced.
    # config.read/.write are left in place — they are owned by migration 0030.
    for role_code, perm_codes in _GRANTS.items():
        for perm_code in perm_codes:
            conn.execute(
                sa.text(
                    "DELETE FROM role_permission "
                    "WHERE role_id = (SELECT id FROM role WHERE code = :role_code) "
                    "AND permission_id = (SELECT id FROM permission WHERE code = :perm_code)"
                ),
                {"role_code": role_code, "perm_code": perm_code},
            )

    conn.execute(
        sa.text(
            "DELETE FROM permission WHERE code IN ('supplier.delete', 'admin.sequence.read')"
        )
    )
