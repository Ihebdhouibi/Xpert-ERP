from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.supplier_invoice.models import (
    SIMatchStatus,
    SupplierInvoice,
    SupplierInvoiceStatus,
)
from app.modules.supplier_invoice.repository import SupplierInvoiceRepository


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

logger = get_logger("supplier_invoice.service")


class SINotFoundError(Exception):
    pass


class SIVersionConflictError(Exception):
    def __init__(self, current: int, submitted: int) -> None:
        self.current_version = current
        self.submitted_version = submitted


class SIInvalidTransitionError(Exception):
    pass


class SISupplierNotFoundError(Exception):
    pass


class SIPONotFoundError(Exception):
    pass


class SIPOLineMissingError(Exception):
    pass


class SIDiscrepancyBlocksApprovalError(Exception):
    pass


# ---------------------------------------------------------------------------
# Three-way match helpers
# ---------------------------------------------------------------------------


def _compute_line_match(
    quantity: int,
    unit_price_ht: int,
    po_quantity_received: int,
    po_unit_price_ht: int,
    tolerance_pct: float,
) -> str:
    if po_quantity_received == 0:
        return SIMatchStatus.qty_mismatch.value

    qty_diff_pct = abs(po_quantity_received - quantity) / po_quantity_received * 100
    if qty_diff_pct > tolerance_pct:
        return SIMatchStatus.qty_mismatch.value

    if po_unit_price_ht > 0:
        price_diff_pct = abs(po_unit_price_ht - unit_price_ht) / po_unit_price_ht * 100
        if price_diff_pct > tolerance_pct:
            return SIMatchStatus.price_mismatch.value

    return SIMatchStatus.ok.value


def _compute_line_totals(quantity: int, unit_price_ht: int, vat_rate: float) -> tuple[int, int]:
    line_total_ht = quantity * unit_price_ht
    line_total_ttc = round(line_total_ht * (1 + vat_rate / 100))
    return line_total_ht, line_total_ttc


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


async def _resolve_supplier(db: AsyncSession, garage_id: int, supplier_public_id: str) -> int:
    from app.modules.supplier.repository import SupplierRepository

    supplier = await SupplierRepository.get_by_public_id(db, garage_id, supplier_public_id)
    if not supplier:
        raise SISupplierNotFoundError(supplier_public_id)
    return supplier.id


async def _resolve_po(db: AsyncSession, garage_id: int, po_public_id: str):  # type: ignore[return]
    from app.modules.purchase_order.repository import PurchaseOrderRepository

    po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, po_public_id)
    if not po:
        raise SIPONotFoundError(po_public_id)
    return po


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_supplier_invoice(
    db: AsyncSession,
    garage_id: int,
    supplier_public_id: str,
    po_public_id: str,
    number: str,
    lines_data: list[dict],
    received_at: Optional[datetime] = None,
    due_date: Optional[date] = None,
    notes: Optional[str] = None,
    user_id: Optional[int] = None,
) -> SupplierInvoice:
    if not lines_data:
        raise SIInvalidTransitionError("A supplier invoice must have at least one line")

    supplier_id = await _resolve_supplier(db, garage_id, supplier_public_id)
    po = await _resolve_po(db, garage_id, po_public_id)

    # Validate all referenced po_line_ids exist on the PO
    po_line_map = {ln.id: ln for ln in po.lines}
    for ld in lines_data:
        if ld["po_line_id"] not in po_line_map:
            raise SIPOLineMissingError(
                f"PO line {ld['po_line_id']} not found on PO {po_public_id}"
            )

    lines = []
    total_ht = 0
    total_ttc = 0
    for ld in lines_data:
        qty = ld["quantity"]
        uph = ld["unit_price_ht"]
        vat = ld.get("vat_rate", 20.0)
        lth, lttc = _compute_line_totals(qty, uph, vat)
        total_ht += lth
        total_ttc += lttc
        po_line = po_line_map[ld["po_line_id"]]
        lines.append(
            {
                "po_line_id": ld["po_line_id"],
                "description": ld.get("description", ""),
                "quantity": qty,
                "unit_price_ht": uph,
                "vat_rate": vat,
                "line_total_ht": lth,
                "line_total_ttc": lttc,
                "match_status": SIMatchStatus.ok.value,
                "po_quantity_ordered": po_line.quantity_ordered,
                "po_quantity_received": po_line.quantity_received,
                "po_unit_price_ht": po_line.unit_price_ht,
            }
        )

    si = await SupplierInvoiceRepository.create(
        db,
        garage_id=garage_id,
        supplier_id=supplier_id,
        purchase_order_id=po.id,
        number=number,
        lines=lines,
        total_ht=total_ht,
        total_ttc=total_ttc,
        received_at=received_at,
        due_date=due_date,
        notes=notes,
        created_by=user_id,
    )
    logger.info("supplier_invoice_created", si_public_id=str(si.public_id), number=number, po_public_id=po_public_id, garage_id=garage_id)
    return si


async def update_supplier_invoice(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
    lines_data: Optional[list[dict]] = None,
    number: Optional[str] = None,
    received_at: Optional[datetime] = None,
    due_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> SupplierInvoice:
    si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
    if not si:
        raise SINotFoundError(public_id)
    if si.version != submitted_version:
        raise SIVersionConflictError(si.version, submitted_version)
    if si.status != SupplierInvoiceStatus.draft:
        raise SIInvalidTransitionError("Only draft supplier invoices can be updated")
    if si.is_exported:
        raise SIInvalidTransitionError("Exported supplier invoices cannot be modified")

    updates: dict = {}
    if number is not None:
        updates["number"] = number
    if received_at is not None:
        updates["received_at"] = received_at
    if due_date is not None:
        updates["due_date"] = due_date
    if notes is not None:
        updates["notes"] = notes

    if lines_data is not None:
        if not lines_data:
            raise SIInvalidTransitionError("A supplier invoice must have at least one line")

        from app.modules.purchase_order.models import PurchaseOrder
        from sqlalchemy import select as sa_select

        po_result = await db.execute(
            sa_select(PurchaseOrder).where(PurchaseOrder.id == si.purchase_order_id)
        )
        po = po_result.scalar_one_or_none()
        if not po:
            raise SIPONotFoundError(str(si.purchase_order_id))

        po_line_map = {ln.id: ln for ln in po.lines}
        lines = []
        total_ht = 0
        total_ttc = 0
        for ld in lines_data:
            if ld["po_line_id"] not in po_line_map:
                raise SIPOLineMissingError(f"PO line {ld['po_line_id']} not found")
            qty = ld["quantity"]
            uph = ld["unit_price_ht"]
            vat = ld.get("vat_rate", 20.0)
            lth, lttc = _compute_line_totals(qty, uph, vat)
            total_ht += lth
            total_ttc += lttc
            po_line = po_line_map[ld["po_line_id"]]
            lines.append(
                {
                    "po_line_id": ld["po_line_id"],
                    "description": ld.get("description", ""),
                    "quantity": qty,
                    "unit_price_ht": uph,
                    "vat_rate": vat,
                    "line_total_ht": lth,
                    "line_total_ttc": lttc,
                    "match_status": SIMatchStatus.ok.value,
                    "po_quantity_ordered": po_line.quantity_ordered,
                    "po_quantity_received": po_line.quantity_received,
                    "po_unit_price_ht": po_line.unit_price_ht,
                }
            )
        updates["lines"] = lines
        updates["total_ht"] = total_ht
        updates["total_ttc"] = total_ttc

    return await SupplierInvoiceRepository.update(db, si, **updates)


# ---------------------------------------------------------------------------
# Three-way match (runs automatically on post)
# ---------------------------------------------------------------------------


async def post_supplier_invoice(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
) -> SupplierInvoice:
    """Run three-way match and transition draft → posted."""
    si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
    if not si:
        raise SINotFoundError(public_id)
    if si.version != submitted_version:
        raise SIVersionConflictError(si.version, submitted_version)
    if si.status != SupplierInvoiceStatus.draft:
        raise SIInvalidTransitionError(
            f"Cannot post a supplier invoice with status '{si.status}'"
        )

    settings = get_settings()
    tolerance = settings.cfg_po_match_tolerance_percent

    from app.modules.purchase_order.models import PurchaseOrderLine
    from sqlalchemy import select as sa_select

    # Fetch current PO line data for match comparison
    po_line_ids = [ln["po_line_id"] for ln in si.lines]
    result = await db.execute(
        sa_select(PurchaseOrderLine).where(PurchaseOrderLine.id.in_(po_line_ids))
    )
    po_line_map = {ln.id: ln for ln in result.scalars().all()}

    matched_lines = []
    has_discrepancy = False

    for line in si.lines:
        po_line = po_line_map.get(line["po_line_id"])
        if po_line is None:
            line = {**line, "match_status": SIMatchStatus.qty_mismatch.value}
            has_discrepancy = True
            matched_lines.append(line)
            continue

        match_status = _compute_line_match(
            quantity=line["quantity"],
            unit_price_ht=line["unit_price_ht"],
            po_quantity_received=po_line.quantity_received,
            po_unit_price_ht=po_line.unit_price_ht,
            tolerance_pct=tolerance,
        )

        matched_lines.append(
            {
                **line,
                "match_status": match_status,
                "po_quantity_ordered": po_line.quantity_ordered,
                "po_quantity_received": po_line.quantity_received,
                "po_unit_price_ht": po_line.unit_price_ht,
            }
        )
        if match_status != SIMatchStatus.ok.value:
            has_discrepancy = True

        # Sync quantity_invoiced on the PO line
        po_line.quantity_invoiced = line["quantity"]

    await db.flush()

    return await SupplierInvoiceRepository.update(
        db,
        si,
        status=SupplierInvoiceStatus.posted,
        lines=matched_lines,
        has_discrepancy=has_discrepancy,
        override_reason=None,
    )


# ---------------------------------------------------------------------------
# Override discrepancy
# ---------------------------------------------------------------------------


async def override_discrepancy(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
    reason: str,
    user_id: Optional[int] = None,
) -> SupplierInvoice:
    """Accept discrepancy with a reason; records an audit entry."""
    si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
    if not si:
        raise SINotFoundError(public_id)
    if si.version != submitted_version:
        raise SIVersionConflictError(si.version, submitted_version)
    if si.status != SupplierInvoiceStatus.posted:
        raise SIInvalidTransitionError(
            "Override is only allowed on posted invoices with discrepancies"
        )
    if not si.has_discrepancy:
        raise SIInvalidTransitionError("No discrepancy to override")
    if not reason or not reason.strip():
        raise SIInvalidTransitionError("Override reason is required")

    # Audit entry
    from sqlalchemy import text as sa_text

    await db.execute(
        sa_text(
            "INSERT INTO audit_log "
            "(garage_id, user_id, component, action, entity_type, entity_id, reason, timestamp) "
            "VALUES (:garage_id, :user_id, :component, :action, :entity_type, :entity_id, :reason, :ts)"
        ),
        {
            "garage_id": garage_id,
            "user_id": user_id,
            "component": "supplier_invoice",
            "action": "discrepancy_override",
            "entity_type": "supplier_invoice",
            "entity_id": si.id,
            "reason": reason,
            "ts": datetime.now(timezone.utc),
        },
    )

    return await SupplierInvoiceRepository.update(
        db,
        si,
        override_reason=reason.strip(),
    )


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


async def approve_supplier_invoice(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
) -> SupplierInvoice:
    si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
    if not si:
        raise SINotFoundError(public_id)
    if si.version != submitted_version:
        raise SIVersionConflictError(si.version, submitted_version)
    if si.status != SupplierInvoiceStatus.posted:
        raise SIInvalidTransitionError(
            f"Cannot approve a supplier invoice with status '{si.status}'"
        )
    if si.has_discrepancy and not si.override_reason:
        raise SIDiscrepancyBlocksApprovalError(
            "Invoice has unresolved discrepancies; provide an override reason before approving"
        )

    return await SupplierInvoiceRepository.update(
        db, si, status=SupplierInvoiceStatus.approved
    )


# ---------------------------------------------------------------------------
# Mark paid
# ---------------------------------------------------------------------------


async def mark_paid(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
) -> SupplierInvoice:
    si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
    if not si:
        raise SINotFoundError(public_id)
    if si.version != submitted_version:
        raise SIVersionConflictError(si.version, submitted_version)
    if si.status != SupplierInvoiceStatus.approved:
        raise SIInvalidTransitionError(
            f"Cannot mark as paid a supplier invoice with status '{si.status}'"
        )

    return await SupplierInvoiceRepository.update(
        db, si, status=SupplierInvoiceStatus.paid
    )


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


async def cancel_supplier_invoice(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
) -> SupplierInvoice:
    si = await SupplierInvoiceRepository.get_by_public_id(db, garage_id, public_id)
    if not si:
        raise SINotFoundError(public_id)
    if si.version != submitted_version:
        raise SIVersionConflictError(si.version, submitted_version)
    if si.status in (SupplierInvoiceStatus.paid, SupplierInvoiceStatus.cancelled):
        raise SIInvalidTransitionError(
            f"Cannot cancel a supplier invoice with status '{si.status}'"
        )
    if si.is_exported:
        raise SIInvalidTransitionError("Exported supplier invoices cannot be cancelled")

    return await SupplierInvoiceRepository.update(
        db, si, status=SupplierInvoiceStatus.cancelled
    )


# ---------------------------------------------------------------------------
# Accounting export (purchases journal)
# ---------------------------------------------------------------------------


def build_accounting_export(si: SupplierInvoice) -> dict:
    """Return a structured journal entry for the purchases journal."""
    return {
        "journal": "purchases",
        "invoice_number": si.number,
        "supplier_invoice_id": str(si.public_id),
        "purchase_order_id": si.purchase_order_id,
        "date": si.received_at.date().isoformat() if si.received_at else None,
        "due_date": si.due_date.isoformat() if si.due_date else None,
        "status": si.status,
        "has_discrepancy": si.has_discrepancy,
        "override_reason": si.override_reason,
        "entries": [
            {
                "account": "607",
                "label": "Achats de marchandises",
                "debit": si.total_ht,
                "credit": 0,
            },
            {
                "account": "44566",
                "label": "TVA déductible",
                "debit": si.total_ttc - si.total_ht,
                "credit": 0,
            },
            {
                "account": "401",
                "label": "Fournisseurs",
                "debit": 0,
                "credit": si.total_ttc,
            },
        ],
        "lines": si.lines,
        "total_ht": si.total_ht,
        "total_ttc": si.total_ttc,
    }
