"""0033 — seed credit_note.* permissions and assign to admin roles

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-06 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

_NEW_PERMISSIONS = [
    {
        "code": "credit_note.read",
        "resource": "credit_note",
        "action": "read",
        "description": "View credit notes",
    },
    {
        "code": "credit_note.create",
        "resource": "credit_note",
        "action": "create",
        "description": "Create draft credit note",
    },
    {
        "code": "credit_note.issue",
        "resource": "credit_note",
        "action": "issue",
        "description": "Issue credit note (assigns CN number)",
    },
    {
        "code": "credit_note.void",
        "resource": "credit_note",
        "action": "void",
        "description": "Void an issued credit note",
    },
]

# Roles that should receive all new permissions
_TARGET_ROLES = ("super_admin", "admin")


def upgrade() -> None:
    conn = op.get_bind()

    # Insert new permissions (skip if already present)
    for perm in _NEW_PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permission (code, description, resource, action) "
                "VALUES (:code, :description, :resource, :action) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            perm,
        )

    # Fetch the IDs of newly inserted permissions
    result = conn.execute(
        sa.text("SELECT id, code FROM permission WHERE code = ANY(:codes)"),
        {"codes": [p["code"] for p in _NEW_PERMISSIONS]},
    )
    perm_map = {row[1]: row[0] for row in result}

    # Fetch target role IDs
    result = conn.execute(
        sa.text("SELECT id, code FROM role WHERE code = ANY(:codes)"),
        {"codes": list(_TARGET_ROLES)},
    )
    role_map = {row[1]: row[0] for row in result}

    # Assign permissions to roles (skip if already assigned)
    for role_code, role_id in role_map.items():
        for perm_code, perm_id in perm_map.items():
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_id, "perm_id": perm_id},
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove role_permission entries for these perms
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE permission_id IN "
            "(SELECT id FROM permission WHERE code = ANY(:codes))"
        ),
        {"codes": [p["code"] for p in _NEW_PERMISSIONS]},
    )

    # Remove the permissions themselves
    conn.execute(
        sa.text("DELETE FROM permission WHERE code = ANY(:codes)"),
        {"codes": [p["code"] for p in _NEW_PERMISSIONS]},
    )
