"""Supplier delivery note (Bon de livraison) reception service.

Creates a BL record linked to a purchase order and performs the goods reception:
- assigns a real part to any "Autre" PO line being received (the swap),
- delegates stock-in + the PO ``quantity_received`` rollup + status + 3-way
  match flag to the existing ``receive_po`` logic,
- records the BL header + lines (with the bl_number correlation key).
"""
from __future__ import annotations

import uuid as uuid_lib
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.modules.documents import repository as doc_repo
from app.modules.ocr import repository as ocr_repo
from app.modules.parts.repository import PartRepository
from app.modules.purchase_order.models import PurchaseOrder
from app.modules.purchase_order.service import receive_po
from app.modules.supplier_delivery_note.models import (
    SupplierDeliveryNote,
    SupplierDeliveryNoteLine,
    SupplierDeliveryNoteStatus,
)

logger = get_logger("supplier_delivery_note.service")


class SDNError(Exception):
    """Base error for the BL reception flow."""


class PONotLinkedError(SDNError):
    """The BL document isn't linked to a purchase order."""


class DuplicateBLNumberError(SDNError):
    def __init__(self, bl_number: str) -> None:
        super().__init__(bl_number)
        self.bl_number = bl_number


class AutreLinePartMissingError(SDNError):
    """An 'Autre' line is being received without a part assigned."""


async def _po_from_document(db: AsyncSession, garage_id: int, document) -> PurchaseOrder:
    if document.owner_entity_type != "purchase_order" or not document.owner_entity_id:
        raise PONotLinkedError("Document is not filed under a purchase order")
    res = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(
            PurchaseOrder.id == document.owner_entity_id,
            PurchaseOrder.garage_id == garage_id,
            PurchaseOrder.deleted_at.is_(None),
        )
    )
    po = res.scalar_one_or_none()
    if po is None:
        raise PONotLinkedError("Linked purchase order not found")
    return po


async def _document_for_extraction(db: AsyncSession, extraction_public_id: uuid_lib.UUID):
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise SDNError("OCR extraction not found")
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    if document is None:
        raise SDNError("Source document not found")
    return document


async def get_po_for_extraction(
    db: AsyncSession, *, garage_id: int, extraction_public_id: uuid_lib.UUID
) -> PurchaseOrder:
    """Resolve the purchase order linked to a BL's OCR extraction."""
    document = await _document_for_extraction(db, extraction_public_id)
    return await _po_from_document(db, garage_id, document)


async def create_delivery_note(
    db: AsyncSession,
    *,
    garage_id: int,
    user_id: Optional[int],
    extraction_public_id: uuid_lib.UUID,
    bl_number: Optional[str],
    bl_date: Optional[date],
    notes: Optional[str],
    lines: list[dict],
    allow_duplicate_bl_number: bool = False,
) -> SupplierDeliveryNote:
    """Create the BL + perform reception.

    ``lines`` = [{"po_line_id": int, "quantity_received": int,
                  "part_public_id": Optional[str]}].
    """
    document = await _document_for_extraction(db, extraction_public_id)
    po = await _po_from_document(db, garage_id, document)

    bl_number = (bl_number or "").strip() or None

    # bl_number uniqueness per (garage, supplier) — warn unless overridden.
    if bl_number and not allow_duplicate_bl_number:
        dup = await db.execute(
            select(SupplierDeliveryNote.id).where(
                SupplierDeliveryNote.garage_id == garage_id,
                SupplierDeliveryNote.supplier_id == po.supplier_id,
                SupplierDeliveryNote.bl_number == bl_number,
            )
        )
        if dup.first() is not None:
            raise DuplicateBLNumberError(bl_number)

    line_map = {ln.id: ln for ln in po.lines}

    # 1. "Autre" swaps — assign a catalogue part to an uncatalogued PO line.
    for item in lines:
        po_line = line_map.get(item["po_line_id"])
        if po_line is None:
            raise SDNError(f"PO line {item['po_line_id']} not found on the order")
        part_public_id = item.get("part_public_id")
        if part_public_id and po_line.part_id is None:
            part = await PartRepository.get_by_public_id(db, garage_id, part_public_id)
            if part is None:
                raise SDNError(f"Part not found: {part_public_id}")
            po_line.part_id = part.id  # the swap (label kept for history)
    await db.flush()

    # 2. Validate: no "Autre" line received without a part.
    for item in lines:
        if item["quantity_received"] > 0 and line_map[item["po_line_id"]].part_id is None:
            raise AutreLinePartMissingError(str(item["po_line_id"]))

    recv_lines = [
        {"line_id": it["po_line_id"], "quantity_received": int(it["quantity_received"])}
        for it in lines
        if it["quantity_received"] > 0
    ]
    if not recv_lines:
        raise SDNError("Aucune quantité à réceptionner.")

    # 3. Stock-in + rollup + status + match via the existing PO reception.
    po = await receive_po(db, garage_id, str(po.public_id), po.version, recv_lines, user_id)
    line_map = {ln.id: ln for ln in po.lines}

    # 4. Record the BL header + lines.
    sdn = SupplierDeliveryNote(
        public_id=uuid_lib.uuid4(),
        garage_id=garage_id,
        purchase_order_id=po.id,
        supplier_id=po.supplier_id,
        bl_number=bl_number,
        bl_date=bl_date,
        document_id=document.id,
        status=SupplierDeliveryNoteStatus.confirmed.value,
        received_by=user_id,
        received_at=datetime.now(timezone.utc),
        notes=(notes or "").strip() or None,
    )
    db.add(sdn)
    await db.flush()

    has_discrepancy = False
    for item in lines:
        if item["quantity_received"] <= 0:
            continue
        po_line = line_map[item["po_line_id"]]
        flag = "ok"
        if po_line.quantity_received > po_line.quantity_ordered:
            flag = "over"
            has_discrepancy = True
        db.add(
            SupplierDeliveryNoteLine(
                supplier_delivery_note_id=sdn.id,
                po_line_id=po_line.id,
                part_id=po_line.part_id,
                # Prefer the BL-captured values; fall back to the PO line.
                description=item.get("designation") or po_line.label,
                quantity=int(item["quantity_received"]),
                unit_price_ht=po_line.unit_price_ht,
                match_flag=flag,
                code=item.get("code"),
                pu_brut=item.get("pu_brut"),
                pu_net=item.get("pu_net"),
                montant_ht=item.get("montant_ht"),
            )
        )
    if has_discrepancy:
        sdn.has_discrepancy = True

    await db.flush()
    logger.info(
        "supplier_delivery_note_created",
        sdn_public_id=str(sdn.public_id),
        po_public_id=str(po.public_id),
        bl_number=bl_number,
        lines=len(recv_lines),
    )
    return sdn
