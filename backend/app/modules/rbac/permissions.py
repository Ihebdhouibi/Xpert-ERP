"""Canonical RBAC permission catalog — the single source of truth.

Every permission code enforced anywhere in the app (via
``require_permission("…")``) MUST appear in :data:`PERMISSIONS` here. This is
verified by ``tests/test_permission_codes.py`` so router/seed drift — the bug
class that left the cash-session, supplier, inspection, config and sequence
pages returning 403 for everyone — can no longer creep back in.

- ``PERMISSIONS`` is consumed by ``app.modules.auth.seed`` (fresh installs,
  via the seed migration) and is the desired end-state for the catalog.
- Numbered Alembic migrations apply *deltas* of this catalog to databases
  that were provisioned before a code was added.

This module imports nothing from the rest of the app so it is safe to import
from migrations, the seed, tests, and routers without any cycle.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Full permission catalog — source of truth from 06_RBAC_DESIGN.md
# ---------------------------------------------------------------------------

PERMISSIONS: list[dict[str, str]] = [
    # --- Identity / system ---
    {"code": "system.settings.read", "resource": "system", "action": "settings.read", "description": "View garage settings"},
    {"code": "system.settings.update", "resource": "system", "action": "settings.update", "description": "Change garage settings"},
    {"code": "system.backup.manage", "resource": "system", "action": "backup.manage", "description": "Trigger backup, view backup status"},
    {"code": "audit.read", "resource": "audit", "action": "read", "description": "View audit log"},
    {"code": "users.read", "resource": "users", "action": "read", "description": "List and view users"},
    {"code": "users.create", "resource": "users", "action": "create", "description": "Create user"},
    {"code": "users.update", "resource": "users", "action": "update", "description": "Update user details"},
    {"code": "users.deactivate", "resource": "users", "action": "deactivate", "description": "Disable user"},
    {"code": "roles.read", "resource": "roles", "action": "read", "description": "View roles and permissions"},
    {"code": "roles.assign", "resource": "roles", "action": "assign", "description": "Assign or revoke roles"},
    {"code": "roles.manage", "resource": "roles", "action": "manage", "description": "Create or edit roles"},
    {"code": "admin.sequence.read", "resource": "admin", "action": "sequence.read", "description": "View document sequence counters"},
    {"code": "config.read", "resource": "config", "action": "read", "description": "View runtime CFG_* settings"},
    {"code": "config.write", "resource": "config", "action": "write", "description": "Create or update runtime CFG_* settings"},
    # --- CRM ---
    {"code": "customer.read", "resource": "customer", "action": "read", "description": "View customers"},
    {"code": "customer.create", "resource": "customer", "action": "create", "description": "Create customer"},
    {"code": "customer.update", "resource": "customer", "action": "update", "description": "Edit customer"},
    {"code": "customer.delete", "resource": "customer", "action": "delete", "description": "Soft delete customer"},
    {"code": "customer.credit_limit.update", "resource": "customer", "action": "credit_limit.update", "description": "Change credit limit"},
    {"code": "customer.balance.read", "resource": "customer", "action": "balance.read", "description": "View ledger and outstanding"},
    {"code": "customer.merge", "resource": "customer", "action": "merge", "description": "Merge duplicate customers"},
    # --- Vehicle ---
    {"code": "vehicle.read", "resource": "vehicle", "action": "read", "description": "View vehicles"},
    {"code": "vehicle.create", "resource": "vehicle", "action": "create", "description": "Create vehicle"},
    {"code": "vehicle.update", "resource": "vehicle", "action": "update", "description": "Edit vehicle"},
    {"code": "vehicle.delete", "resource": "vehicle", "action": "delete", "description": "Soft delete vehicle"},
    # --- Repair Order / Workshop ---
    {"code": "repair_order.read", "resource": "repair_order", "action": "read", "description": "View repair orders"},
    {"code": "repair_order.create", "resource": "repair_order", "action": "create", "description": "Create repair order"},
    {"code": "repair_order.update", "resource": "repair_order", "action": "update", "description": "Edit repair order details"},
    {"code": "repair_order.delete", "resource": "repair_order", "action": "delete", "description": "Soft delete repair order"},
    {"code": "repair_order.assign", "resource": "repair_order", "action": "assign", "description": "Assign or reassign mechanic"},
    {"code": "repair_order.transition", "resource": "repair_order", "action": "transition", "description": "Change status"},
    {"code": "repair_order.transition.cancel", "resource": "repair_order", "action": "transition.cancel", "description": "Move to cancelled"},
    {"code": "repair_order.line.manage", "resource": "repair_order", "action": "line.manage", "description": "Add/edit/remove labor and part lines"},
    {"code": "repair_order.time_entry.manage", "resource": "repair_order", "action": "time_entry.manage", "description": "Start/stop time tracking"},
    {"code": "repair_order.media.upload", "resource": "repair_order", "action": "media.upload", "description": "Attach photos and videos"},
    {"code": "inspection.read", "resource": "inspection", "action": "read", "description": "View inspections"},
    {"code": "inspection.execute", "resource": "inspection", "action": "execute", "description": "Perform inspection"},
    {"code": "inspection.template.manage", "resource": "inspection", "action": "template.manage", "description": "Create or edit inspection templates"},
    # --- Inventory ---
    {"code": "part.read", "resource": "part", "action": "read", "description": "View parts"},
    {"code": "part.create", "resource": "part", "action": "create", "description": "Create part"},
    {"code": "part.update", "resource": "part", "action": "update", "description": "Edit part"},
    {"code": "part.delete", "resource": "part", "action": "delete", "description": "Deactivate part"},
    {"code": "stock.movement.read", "resource": "stock", "action": "movement.read", "description": "View stock movements"},
    {"code": "stock.movement.create", "resource": "stock", "action": "movement.create", "description": "Record stock movement"},
    {"code": "stock.movement.adjust", "resource": "stock", "action": "movement.adjust", "description": "Manual stock adjustment"},
    {"code": "stock.reservation.manage", "resource": "stock", "action": "reservation.manage", "description": "Reserve or release stock"},
    {"code": "stock.alert.read", "resource": "stock", "action": "alert.read", "description": "View low-stock alerts"},
    # --- Quotation / Invoice ---
    {"code": "quotation.read", "resource": "quotation", "action": "read", "description": "View quotations"},
    {"code": "quotation.create", "resource": "quotation", "action": "create", "description": "Create quotation"},
    {"code": "quotation.update", "resource": "quotation", "action": "update", "description": "Edit quotation"},
    {"code": "quotation.send", "resource": "quotation", "action": "send", "description": "Send quotation to customer"},
    {"code": "quotation.approve_on_behalf", "resource": "quotation", "action": "approve_on_behalf", "description": "Internally mark approved"},
    {"code": "quotation.convert", "resource": "quotation", "action": "convert", "description": "Convert to invoice or repair order"},
    {"code": "invoice.read", "resource": "invoice", "action": "read", "description": "View invoices"},
    {"code": "invoice.create", "resource": "invoice", "action": "create", "description": "Create invoice"},
    {"code": "invoice.update", "resource": "invoice", "action": "update", "description": "Edit invoice (draft only)"},
    {"code": "invoice.issue", "resource": "invoice", "action": "issue", "description": "Issue invoice (locks document number)"},
    {"code": "invoice.cancel", "resource": "invoice", "action": "cancel", "description": "Cancel or issue credit note"},
    {"code": "invoice.discount.apply", "resource": "invoice", "action": "discount.apply", "description": "Apply discount above standard threshold"},
    {"code": "invoice.credit_limit.override", "resource": "invoice", "action": "credit_limit.override", "description": "Override customer credit limit block"},
    # --- Payment / Cash Register ---
    {"code": "payment.read", "resource": "payment", "action": "read", "description": "View payments"},
    {"code": "payment.record", "resource": "payment", "action": "record", "description": "Record payment"},
    {"code": "payment.cancel", "resource": "payment", "action": "cancel", "description": "Cancel payment"},
    {"code": "deposit.record", "resource": "deposit", "action": "record", "description": "Record deposit"},
    {"code": "cash_session.open", "resource": "cash_session", "action": "open", "description": "Open cash session"},
    {"code": "cash_session.close", "resource": "cash_session", "action": "close", "description": "Close cash session"},
    {"code": "cash_session.read", "resource": "cash_session", "action": "read", "description": "View session details"},
    {"code": "refund.execute", "resource": "refund", "action": "execute", "description": "Execute refund"},
    {"code": "credit_note.read", "resource": "credit_note", "action": "read", "description": "View credit notes"},
    {"code": "credit_note.create", "resource": "credit_note", "action": "create", "description": "Create draft credit note"},
    {"code": "credit_note.issue", "resource": "credit_note", "action": "issue", "description": "Issue credit note (assigns CN number)"},
    {"code": "credit_note.void", "resource": "credit_note", "action": "void", "description": "Void an issued credit note"},
    # --- Supplier / Purchasing ---
    {"code": "supplier.read", "resource": "supplier", "action": "read", "description": "View suppliers"},
    {"code": "supplier.create", "resource": "supplier", "action": "create", "description": "Create supplier"},
    {"code": "supplier.update", "resource": "supplier", "action": "update", "description": "Edit supplier"},
    {"code": "supplier.delete", "resource": "supplier", "action": "delete", "description": "Delete supplier"},
    {"code": "purchase_request.create", "resource": "purchase_request", "action": "create", "description": "Create purchase request"},
    {"code": "purchase_order.read", "resource": "purchase_order", "action": "read", "description": "View purchase orders"},
    {"code": "purchase_order.create", "resource": "purchase_order", "action": "create", "description": "Create purchase order"},
    {"code": "purchase_order.approve", "resource": "purchase_order", "action": "approve", "description": "Approve purchase request/order"},
    {"code": "purchase_order.send", "resource": "purchase_order", "action": "send", "description": "Send PO to supplier"},
    {"code": "purchase_order.reception.record", "resource": "purchase_order", "action": "reception.record", "description": "Record reception"},
    {"code": "supplier_invoice.record", "resource": "supplier_invoice", "action": "record", "description": "Attach supplier invoice"},
    {"code": "supplier_invoice.read", "resource": "supplier_invoice", "action": "read", "description": "View supplier invoices"},
    {"code": "supplier_invoice.create", "resource": "supplier_invoice", "action": "create", "description": "Create supplier invoices"},
    {"code": "supplier_invoice.post", "resource": "supplier_invoice", "action": "post", "description": "Post and run three-way match"},
    {"code": "supplier_invoice.approve", "resource": "supplier_invoice", "action": "approve", "description": "Approve supplier invoices"},
    {"code": "supplier_invoice.override", "resource": "supplier_invoice", "action": "override", "description": "Override discrepancies"},
    # --- Bon de retour (return note) ---
    {"code": "bon_de_retour.read", "resource": "bon_de_retour", "action": "read", "description": "View bon de retour"},
    {"code": "bon_de_retour.create", "resource": "bon_de_retour", "action": "create", "description": "Create draft bon de retour"},
    {"code": "bon_de_retour.update", "resource": "bon_de_retour", "action": "update", "description": "Edit a draft bon de retour"},
    {"code": "bon_de_retour.confirm", "resource": "bon_de_retour", "action": "confirm", "description": "Confirm bon de retour (assign number, move stock)"},
    {"code": "bon_de_retour.cancel", "resource": "bon_de_retour", "action": "cancel", "description": "Cancel a draft bon de retour"},
    {"code": "bon_de_retour.reverse", "resource": "bon_de_retour", "action": "reverse", "description": "Reverse a confirmed bon de retour (undo stock movements)"},
    # --- Supplier credit note (avoir fournisseur) ---
    {"code": "supplier_credit_note.read", "resource": "supplier_credit_note", "action": "read", "description": "View supplier credit notes (avoir fournisseur)"},
    {"code": "supplier_credit_note.create", "resource": "supplier_credit_note", "action": "create", "description": "Create a supplier credit note"},
    {"code": "supplier_credit_note.issue", "resource": "supplier_credit_note", "action": "issue", "description": "Issue a supplier credit note"},
    {"code": "supplier_credit_note.void", "resource": "supplier_credit_note", "action": "void", "description": "Void a supplier credit note"},
    # --- Notifications ---
    {"code": "notification.read", "resource": "notification", "action": "read", "description": "View delivery log"},
    {"code": "notification.send", "resource": "notification", "action": "send", "description": "Send manual notification"},
    {"code": "notification.template.manage", "resource": "notification", "action": "template.manage", "description": "Edit notification templates"},
    # --- Documents / OCR ---
    {"code": "document.read", "resource": "document", "action": "read", "description": "View document metadata"},
    {"code": "document.download", "resource": "document", "action": "download", "description": "Download via signed URL"},
    {"code": "document.upload", "resource": "document", "action": "upload", "description": "Upload document"},
    {"code": "document.delete", "resource": "document", "action": "delete", "description": "Soft delete document"},
    {"code": "ocr.execute", "resource": "ocr", "action": "execute", "description": "Run OCR on a document"},
    {"code": "ocr.confirm", "resource": "ocr", "action": "confirm", "description": "Confirm OCR extraction and apply"},
    # --- Reporting ---
    {"code": "reporting.dashboard.read", "resource": "reporting", "action": "dashboard.read", "description": "KPI dashboard"},
    {"code": "reporting.revenue.read", "resource": "reporting", "action": "revenue.read", "description": "Revenue reports"},
    {"code": "reporting.workshop.read", "resource": "reporting", "action": "workshop.read", "description": "Workshop KPI"},
    {"code": "reporting.inventory.read", "resource": "reporting", "action": "inventory.read", "description": "Inventory KPI"},
    {"code": "reporting.accounting.export", "resource": "reporting", "action": "accounting.export", "description": "Accounting export"},
    {"code": "accounting_export.read", "resource": "accounting_export", "action": "read", "description": "View accounting exports"},
    {"code": "accounting_export.create", "resource": "accounting_export", "action": "create", "description": "Trigger accounting export"},
    {"code": "accounting_export.download", "resource": "accounting_export", "action": "download", "description": "Download accounting export file"},
]

# Fast membership set of every valid permission code.
ALL_PERMISSION_CODES: frozenset[str] = frozenset(p["code"] for p in PERMISSIONS)
