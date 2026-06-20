"""0045 — idempotent backfill for migrations 0037-0040

Migrations 0037-0040 were applied inside a single SQLAlchemy transaction
(engine.begin() in main.py lifespan). When migration 0042 (create
bon_de_retour) failed on databases that already had those tables from the
previous numbering scheme, the entire transaction rolled back — taking
0037-0041 with it. The alembic_version was then manually stamped to 0043
to unblock startup, leaving the schema incomplete.

This migration re-applies every change from 0037-0040 using IF NOT EXISTS /
ON CONFLICT DO NOTHING so it is safe on:
  * affected databases (columns/tables are missing — they get created)
  * clean installs    (columns/tables already exist — the IF NOT EXISTS is a no-op)

Changes restored:
  0037  repair_order.diagnosis (JSONB) + diagnosis_completed_at
  0038  app_notification table + indexes
  0039  supplier.delete / admin.sequence.read permission seeding
  0040  cash_session.opening_float

Revision ID: 0045
Revises: 0044
Create Date: 2026-06-20 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# 0039 data — permissions / grants
# ---------------------------------------------------------------------------
_PERMISSIONS = [
    {"code": "supplier.delete",      "resource": "supplier", "action": "delete",       "description": "Delete supplier"},
    {"code": "admin.sequence.read",  "resource": "admin",    "action": "sequence.read", "description": "View document sequence counters"},
    {"code": "config.read",          "resource": "config",   "action": "read",          "description": "View runtime CFG_* settings"},
    {"code": "config.write",         "resource": "config",   "action": "write",         "description": "Create or update runtime CFG_* settings"},
]

_GRANTS: dict[str, list[str]] = {
    "super_admin":      ["supplier.delete", "admin.sequence.read", "config.read", "config.write"],
    "admin":            ["supplier.delete", "admin.sequence.read", "config.read", "config.write"],
    "inventory_manager": ["supplier.delete"],
    "accountant":       ["admin.sequence.read"],
}


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0037 — repair_order: diagnosis fields
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE repair_order"
        " ADD COLUMN IF NOT EXISTS diagnosis JSONB"
    )
    op.execute(
        "ALTER TABLE repair_order"
        " ADD COLUMN IF NOT EXISTS diagnosis_completed_at TIMESTAMP WITH TIME ZONE"
    )

    # ------------------------------------------------------------------
    # 0038 — app_notification table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_notification (
            id          BIGSERIAL PRIMARY KEY,
            garage_id   BIGINT NOT NULL,
            recipient_id BIGINT NOT NULL,
            title       VARCHAR(255) NOT NULL,
            body        TEXT,
            link        VARCHAR(500),
            read_at     TIMESTAMP WITH TIME ZONE,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_app_notification_garage_id"
        " ON app_notification (garage_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_app_notification_recipient_id"
        " ON app_notification (recipient_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_app_notification_recipient"
        " ON app_notification (recipient_id, read_at)"
    )

    # ------------------------------------------------------------------
    # 0039 — seed missing RBAC permissions
    # ------------------------------------------------------------------
    conn = op.get_bind()
    for perm in _PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permission (code, description, resource, action)"
                " VALUES (:code, :description, :resource, :action)"
                " ON CONFLICT (code) DO NOTHING"
            ),
            perm,
        )
    for role_code, perm_codes in _GRANTS.items():
        for perm_code in perm_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id)"
                    " SELECT r.id, p.id FROM role r, permission p"
                    " WHERE r.code = :role_code AND p.code = :perm_code"
                    " ON CONFLICT DO NOTHING"
                ),
                {"role_code": role_code, "perm_code": perm_code},
            )

    # ------------------------------------------------------------------
    # 0040 — cash_session: opening_float
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE cash_session"
        " ADD COLUMN IF NOT EXISTS opening_float BIGINT NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE cash_session DROP COLUMN IF EXISTS opening_float")

    conn = op.get_bind()
    for role_code, perm_codes in _GRANTS.items():
        for perm_code in perm_codes:
            conn.execute(
                sa.text(
                    "DELETE FROM role_permission"
                    " WHERE role_id = (SELECT id FROM role WHERE code = :role_code)"
                    " AND permission_id = (SELECT id FROM permission WHERE code = :perm_code)"
                ),
                {"role_code": role_code, "perm_code": perm_code},
            )
    conn.execute(
        sa.text("DELETE FROM permission WHERE code IN ('supplier.delete', 'admin.sequence.read')")
    )

    op.execute("DROP INDEX IF EXISTS ix_app_notification_recipient")
    op.execute("DROP INDEX IF EXISTS ix_app_notification_recipient_id")
    op.execute("DROP INDEX IF EXISTS ix_app_notification_garage_id")
    op.execute("DROP TABLE IF EXISTS app_notification")

    op.execute("ALTER TABLE repair_order DROP COLUMN IF EXISTS diagnosis_completed_at")
    op.execute("ALTER TABLE repair_order DROP COLUMN IF EXISTS diagnosis")
