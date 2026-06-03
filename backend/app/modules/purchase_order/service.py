from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.purchase_order.models import (
    POMatchFlag,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)
from app.modules.purchase_order.repository import (
    PurchaseOrderLineRepository,
    PurchaseOrderRepository,
)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

logger = get_logger("purchase_order.service")


class PONotFoundError(Exception):
    pass


class POVersionConflictError(Exception):
    def __init__(self, current: int, submitted: int) -> None:
        self.current_version = current
        self.submitted_version = submitted


class POInvalidTransitionError(Exception):
    pass


class POLineNotFoundError(Exception):
    pass


class SupplierNotFoundForPOError(Exception):
    pass


class PartNotFoundForPOError(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_total_ht(lines_data: list[dict]) -> int:
    return sum(d["quantity_ordered"] * d["unit_price_ht"] for d in lines_data)


def _recompute_total_from_lines(lines: list[PurchaseOrderLine]) -> int:
    return sum(ln.quantity_ordered * ln.unit_price_ht for ln in lines)


async def _resolve_supplier(db: AsyncSession, garage_id: int, supplier_public_id: str) -> int:
    from app.modules.supplier.repository import SupplierRepository

    supplier = await SupplierRepository.get_by_public_id(db, garage_id, supplier_public_id)
    if not supplier:
        raise SupplierNotFoundForPOError(supplier_public_id)
    return supplier.id


async def _resolve_part(db: AsyncSession, garage_id: int, part_public_id: str) -> int:
    from app.modules.parts.repository import PartRepository

    part = await PartRepository.get_by_public_id(db, garage_id, part_public_id)
    if not part:
        raise PartNotFoundForPOError(part_public_id)
    return part.id


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_po(
    db: AsyncSession,
    garage_id: int,
    supplier_public_id: str,
    lines_data: list[dict],
    expected_delivery_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> PurchaseOrder:
    if not lines_data:
        raise POInvalidTransitionError("A purchase order must have at least one line")

    supplier_id = await _resolve_supplier(db, garage_id, supplier_public_id)

    # Generate doc number
    from app.modules.sequence import service as seq_svc
    seq = await seq_svc.next(db, garage_id=garage_id, doc_type="PO")
    doc_number = seq.formatted

    total_ht = _compute_total_ht(lines_data)
    po = await PurchaseOrderRepository.create(
        db,
        garage_id=garage_id,
        supplier_id=supplier_id,
        doc_number=doc_number,
        expected_delivery_date=expected_delivery_date,
        notes=notes,
        total_ht=total_ht,
    )

    for ld in lines_data:
        part_id = await _resolve_part(db, garage_id, ld["part_public_id"])
        await PurchaseOrderLineRepository.create(
            db,
            po_id=po.id,
            part_id=part_id,
            quantity_ordered=ld["quantity_ordered"],
            unit_price_ht=ld["unit_price_ht"],
        )

    logger.info(
        "purchase_order_created",
        po_public_id=str(po.public_id),
        doc_number=doc_number,
        supplier_public_id=supplier_public_id,
        garage_id=garage_id,
        total_ht=total_ht,
    )
    return po


async def update_po(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
    lines_data: Optional[list[dict]] = None,
    expected_delivery_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> PurchaseOrder:
    po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, public_id)
    if not po:
        raise PONotFoundError(public_id)
    if po.version != submitted_version:
        raise POVersionConflictError(po.version, submitted_version)
    if po.status != PurchaseOrderStatus.draft:
        raise POInvalidTransitionError("Only draft purchase orders can be updated")

    updates: dict = {}
    if expected_delivery_date is not None:
        updates["expected_delivery_date"] = expected_delivery_date
    if notes is not None:
        updates["notes"] = notes

    if lines_data is not None:
        if not lines_data:
            raise POInvalidTransitionError("A purchase order must have at least one line")
        await PurchaseOrderLineRepository.delete_all_for_po(db, po.id)
        for ld in lines_data:
            part_id = await _resolve_part(db, garage_id, ld["part_public_id"])
            await PurchaseOrderLineRepository.create(
                db,
                po_id=po.id,
                part_id=part_id,
                quantity_ordered=ld["quantity_ordered"],
                unit_price_ht=ld["unit_price_ht"],
            )
        # Refresh lines to recompute total
        await db.refresh(po, ["lines"])
        updates["total_ht"] = _recompute_total_from_lines(po.lines)

    return await PurchaseOrderRepository.update(db, po, **updates)


async def send_po(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
) -> PurchaseOrder:
    po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, public_id)
    if not po:
        raise PONotFoundError(public_id)
    if po.version != submitted_version:
        raise POVersionConflictError(po.version, submitted_version)
    if po.status != PurchaseOrderStatus.draft:
        raise POInvalidTransitionError(
            f"Cannot send a PO with status '{po.status}'"
        )
    if not po.lines:
        raise POInvalidTransitionError("Cannot send a purchase order with no lines")

    return await PurchaseOrderRepository.update(
        db, po, status=PurchaseOrderStatus.sent
    )


async def receive_po(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
    lines: list[dict],
    user_id: Optional[int] = None,
) -> PurchaseOrder:
    """
    lines = [{"line_id": int, "quantity_received": int}, ...]
    Stock movements are created atomically in the same flush batch.
    """
    po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, public_id)
    if not po:
        raise PONotFoundError(public_id)
    if po.version != submitted_version:
        raise POVersionConflictError(po.version, submitted_version)
    if po.status not in (PurchaseOrderStatus.sent, PurchaseOrderStatus.partially_received):
        raise POInvalidTransitionError(
            f"Cannot receive a PO with status '{po.status}'"
        )

    settings = get_settings()
    tolerance = settings.cfg_po_match_tolerance_percent

    from app.modules.parts.stock_service import record_movement
    from app.modules.parts.stock_models import StockMovementType

    # Build line_id → line map for quick access
    line_map = {ln.id: ln for ln in po.lines}

    for item in lines:
        line_id = item["line_id"]
        qty = item["quantity_received"]
        if qty <= 0:
            continue

        line = line_map.get(line_id)
        if not line:
            raise POLineNotFoundError(f"Line {line_id} not found on PO {public_id}")

        # Update received quantity (no over-reception guard; partial is OK)
        line.quantity_received += qty

        # Create stock-in movement atomically (flush happens inside record_movement)
        await record_movement(
            db,
            garage_id=garage_id,
            part_id=line.part_id,
            movement_type=StockMovementType.in_,
            quantity=qty,
            unit_cost_minor=line.unit_price_ht,
            ref_type="purchase_order",
            ref_id=str(po.public_id),
            reason=f"Reception for PO {po.doc_number}",
            created_by_user_id=user_id,
            allow_negative=False,
        )

        # Recompute three-way match flag
        line.match_flag = PurchaseOrderLineRepository.compute_match_flag(
            line.quantity_ordered,
            line.quantity_received,
            line.quantity_invoiced,
            tolerance,
        )

    await db.flush()

    # Determine new PO status
    all_received = all(
        ln.quantity_received >= ln.quantity_ordered for ln in po.lines
    )
    any_received = any(ln.quantity_received > 0 for ln in po.lines)

    new_status = (
        PurchaseOrderStatus.completed
        if all_received
        else PurchaseOrderStatus.partially_received
        if any_received
        else po.status
    )

    result = await PurchaseOrderRepository.update(db, po, status=new_status)
    logger.info(
        "purchase_order_received",
        po_public_id=str(po.public_id),
        doc_number=po.doc_number,
        new_status=new_status.value,
        garage_id=garage_id,
    )
    return result


async def cancel_po(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
) -> PurchaseOrder:
    po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, public_id)
    if not po:
        raise PONotFoundError(public_id)
    if po.version != submitted_version:
        raise POVersionConflictError(po.version, submitted_version)
    if po.status in (PurchaseOrderStatus.completed, PurchaseOrderStatus.cancelled):
        raise POInvalidTransitionError(
            f"Cannot cancel a PO with status '{po.status}'"
        )

    return await PurchaseOrderRepository.update(
        db, po, status=PurchaseOrderStatus.cancelled
    )


async def update_invoiced_qty(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    line_id: int,
    quantity_invoiced: int,
) -> PurchaseOrderLine:
    po = await PurchaseOrderRepository.get_by_public_id(db, garage_id, public_id)
    if not po:
        raise PONotFoundError(public_id)

    line = await PurchaseOrderLineRepository.get_by_id(db, line_id, po.id)
    if not line:
        raise POLineNotFoundError(f"Line {line_id}")

    settings = get_settings()
    line.quantity_invoiced = quantity_invoiced
    line.match_flag = PurchaseOrderLineRepository.compute_match_flag(
        line.quantity_ordered,
        line.quantity_received,
        line.quantity_invoiced,
        settings.cfg_po_match_tolerance_percent,
    )
    await db.flush()
    return line


async def create_po_from_alert(
    db: AsyncSession,
    garage_id: int,
    alert_id: int,
    supplier_public_id: str,
    unit_price_ht: int,
    user_id: Optional[int] = None,
) -> PurchaseOrder:
    """Create a draft PO with one line derived from a low-stock alert."""
    from app.modules.parts.stock_models import LowStockAlert
    from app.modules.parts.stock_repository import StockRepository
    from sqlalchemy import select

    alert = await StockRepository.get_alert(db, garage_id, alert_id)
    if not alert:
        raise PONotFoundError(f"Alert {alert_id} not found")

    # Resolve part public_id
    from app.modules.parts.models import Part
    result = await db.execute(select(Part).where(Part.id == alert.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise PartNotFoundForPOError(str(alert.part_id))

    quantity = alert.suggested_reorder_quantity or 1
    return await create_po(
        db,
        garage_id=garage_id,
        supplier_public_id=supplier_public_id,
        lines_data=[
            {
                "part_public_id": str(part.public_id),
                "quantity_ordered": quantity,
                "unit_price_ht": unit_price_ht,
            }
        ],
        notes=f"Auto-created from low-stock alert #{alert_id}",
    )
