"""Seed data for roles and the full permission catalog.

Run via: alembic upgrade head  (the seed migration calls seed_all)
Or directly: python -m app.modules.auth.seed
"""
from __future__ import annotations

from typing import Any

# The permission catalog lives in the canonical registry so routers, the seed
# and migrations all share one source of truth. Re-exported here because the
# initial seed migration (0001) imports PERMISSIONS from this module.
from app.modules.rbac.permissions import PERMISSIONS  # noqa: F401

# ---------------------------------------------------------------------------
# Role definitions (system roles — garage_id = NULL)
# ---------------------------------------------------------------------------

ROLES: list[dict[str, Any]] = [
    {"code": "super_admin", "display_name": "Super Administrator", "is_system": True},
    {"code": "admin", "display_name": "Administrator", "is_system": True},
    {"code": "secretary", "display_name": "Secretary / Reception", "is_system": True},
    {"code": "mechanic", "display_name": "Mechanic", "is_system": True},
    {"code": "inventory_manager", "display_name": "Inventory Manager", "is_system": True},
    {"code": "accountant", "display_name": "Accountant", "is_system": True},
    {"code": "read_only", "display_name": "Read Only", "is_system": True},
]

# ---------------------------------------------------------------------------
# Role-to-permission assignments (system defaults from RBAC design matrix)
# A = grant, R = grant (read-only variant same code), O = optional (grant), - = skip
# ---------------------------------------------------------------------------

# All permissions granted to super_admin and admin
_ALL = {p["code"] for p in PERMISSIONS}

_SECRETARY = {
    "system.settings.read",
    "customer.read", "customer.create", "customer.update",
    "customer.balance.read",
    "vehicle.read", "vehicle.create", "vehicle.update",
    "repair_order.read", "repair_order.create", "repair_order.update",
    "repair_order.assign", "repair_order.transition",
    "repair_order.line.manage", "repair_order.media.upload",
    "inspection.read",
    "part.read",
    "stock.movement.read", "stock.alert.read",
    "quotation.read", "quotation.create", "quotation.update",
    "quotation.send", "quotation.approve_on_behalf", "quotation.convert",
    "invoice.read", "invoice.create", "invoice.update", "invoice.issue",
    "payment.read", "payment.record",
    "deposit.record",
    "cash_session.open", "cash_session.close", "cash_session.read",
    "supplier.read", "supplier.create", "supplier.update",
    "purchase_request.create",
    "notification.read",
    "document.read", "document.download", "document.upload",
    "reporting.dashboard.read",
}

_MECHANIC = {
    "customer.read",
    "vehicle.read",
    "repair_order.read", "repair_order.transition",
    "repair_order.time_entry.manage", "repair_order.media.upload",
    "inspection.read", "inspection.execute",
    "part.read",
    "stock.movement.read",
    "quotation.read",
    "invoice.read",
    "payment.read",
    "reporting.dashboard.read", "reporting.workshop.read",
}

_INVENTORY_MANAGER = {
    "customer.read",
    "vehicle.read",
    "repair_order.read",
    "part.read", "part.create", "part.update",
    "stock.movement.read", "stock.movement.create", "stock.movement.adjust",
    "stock.reservation.manage", "stock.alert.read",
    "supplier.read", "supplier.create", "supplier.update", "supplier.delete",
    "purchase_request.create",
    "purchase_order.read", "purchase_order.create", "purchase_order.approve",
    "purchase_order.send", "purchase_order.reception.record",
    "supplier_invoice.record",
    "reporting.dashboard.read", "reporting.inventory.read",
}

_ACCOUNTANT = {
    "system.settings.read",
    "audit.read",
    "admin.sequence.read",
    "customer.read", "customer.balance.read",
    "vehicle.read",
    "repair_order.read",
    "part.read",
    "stock.movement.read",
    "quotation.read",
    "invoice.read",
    "payment.read",
    "cash_session.read",
    "supplier.read",
    "reporting.dashboard.read", "reporting.revenue.read",
    "reporting.workshop.read", "reporting.inventory.read",
    "reporting.accounting.export",
    "document.read", "document.download",
}

_READ_ONLY = {
    "system.settings.read",
    "audit.read",
    "users.read",
    "customer.read", "customer.balance.read",
    "vehicle.read",
    "repair_order.read",
    "part.read",
    "stock.movement.read", "stock.alert.read",
    "quotation.read",
    "invoice.read",
    "payment.read",
    "cash_session.read",
    "supplier.read",
    "reporting.dashboard.read", "reporting.revenue.read",
    "reporting.workshop.read", "reporting.inventory.read",
    "document.read",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": _ALL,
    "admin": _ALL,
    "secretary": _SECRETARY,
    "mechanic": _MECHANIC,
    "inventory_manager": _INVENTORY_MANAGER,
    "accountant": _ACCOUNTANT,
    "read_only": _READ_ONLY,
}
