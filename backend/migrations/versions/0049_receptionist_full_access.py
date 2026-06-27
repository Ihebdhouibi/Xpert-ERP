"""Grant full non-administration access to the receptionist role.

The receptionist gets all operational permissions (CRM, workshop, billing,
purchasing, stock, reporting, documents) but NOT:
  - Administration (users, roles, settings, audit, sequences, config)
  - Credit limit controls (credit_limit.update, credit_limit.override,
    credit.override.manage)
  - Inspection/notification template management (admin-only authoring)

Revision ID: 0049
Revises: 0048
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

_RECEPTIONIST_PERMISSIONS = [
    # CRM
    "customer.read", "customer.create", "customer.update", "customer.delete",
    "customer.balance.read",
    # Vehicle
    "vehicle.read", "vehicle.create", "vehicle.update", "vehicle.delete",
    # Repair Order / Workshop
    "repair_order.read", "repair_order.create", "repair_order.update",
    "repair_order.delete", "repair_order.assign", "repair_order.transition",
    "repair_order.transition.cancel", "repair_order.line.manage",
    "repair_order.time_entry.manage", "repair_order.media.upload",
    # Inspection (execute only — template authoring stays admin)
    "inspection.read", "inspection.execute",
    # Parts / Stock
    "part.read", "part.create", "part.update", "part.delete",
    "stock.movement.read", "stock.movement.create", "stock.movement.adjust",
    "stock.reservation.manage", "stock.alert.read",
    # Quotation / Invoice
    "quotation.read", "quotation.create", "quotation.update", "quotation.send",
    "quotation.approve_on_behalf", "quotation.convert",
    "invoice.read", "invoice.create", "invoice.update", "invoice.issue",
    "invoice.cancel", "invoice.discount.apply",
    # Payment / Cash Register
    "payment.read", "payment.record", "payment.cancel",
    "deposit.record",
    "cash_session.open", "cash_session.close", "cash_session.read",
    "refund.execute",
    "credit_note.read", "credit_note.create", "credit_note.issue", "credit_note.void",
    # Supplier / Purchasing
    "supplier.read", "supplier.create", "supplier.update", "supplier.delete",
    "purchase_request.create",
    "purchase_order.read", "purchase_order.create", "purchase_order.approve",
    "purchase_order.send", "purchase_order.reception.record",
    "supplier_invoice.record", "supplier_invoice.read", "supplier_invoice.create",
    "supplier_invoice.post", "supplier_invoice.approve", "supplier_invoice.override",
    # Bon de retour
    "bon_de_retour.read", "bon_de_retour.create", "bon_de_retour.update",
    "bon_de_retour.confirm", "bon_de_retour.cancel", "bon_de_retour.reverse",
    # Supplier credit note
    "supplier_credit_note.read", "supplier_credit_note.create",
    "supplier_credit_note.issue", "supplier_credit_note.void",
    # Notifications (read/send — template authoring stays admin)
    "notification.read", "notification.send",
    # Documents / OCR
    "document.read", "document.download", "document.upload", "document.delete",
    "ocr.execute", "ocr.confirm",
    # Reporting
    "reporting.dashboard.read", "reporting.revenue.read", "reporting.workshop.read",
    "reporting.inventory.read", "reporting.accounting.export",
    "accounting_export.read", "accounting_export.create", "accounting_export.download",
]


def upgrade() -> None:
    conn = op.get_bind()

    for perm_code in _RECEPTIONIST_PERMISSIONS:
        conn.execute(
            sa.text(
                """
                INSERT INTO role_permission (role_id, permission_id)
                SELECT r.id, p.id
                FROM role r
                CROSS JOIN permission p
                WHERE r.code = 'receptionist'
                  AND p.code = :perm_code
                  AND NOT EXISTS (
                      SELECT 1 FROM role_permission rp
                      WHERE rp.role_id = r.id AND rp.permission_id = p.id
                  )
                """
            ),
            {"perm_code": perm_code},
        )


def downgrade() -> None:
    conn = op.get_bind()

    for perm_code in _RECEPTIONIST_PERMISSIONS:
        conn.execute(
            sa.text(
                """
                DELETE FROM role_permission
                WHERE role_id = (SELECT id FROM role WHERE code = 'receptionist')
                  AND permission_id = (SELECT id FROM permission WHERE code = :perm_code)
                """
            ),
            {"perm_code": perm_code},
        )
