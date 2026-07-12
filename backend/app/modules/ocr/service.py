"""OCR pipeline business logic.

Critical safety rule:
    Fields whose OCR confidence is BELOW the configured threshold for that field
    are flagged as `needs_review` and are NEVER auto-written to any other table.
    Only `confirm_fields()` — triggered by an explicit human action — may write
    confirmed values to vehicle / customer models.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.customer import repository as customer_repo
from app.modules.documents import repository as doc_repo
from app.modules.documents import storage as doc_storage
from app.modules.documents.models import DocumentCategory, OwnerEntityType
from app.modules.ocr import extractors
from app.modules.ocr import repository as ocr_repo
from app.modules.ocr.engine import RawOcrResult, get_ocr_engine
from app.modules.ocr.extractors import FieldMap
from app.modules.ocr.models import OcrExtraction, OcrStatus
from app.modules.vehicles import repository as vehicle_repo

logger = get_logger("ocr.service")

# Categories that trigger OCR automatically on upload
OCR_TRIGGER_CATEGORIES = {
    DocumentCategory.registration_card,
    DocumentCategory.id_doc,
    DocumentCategory.supplier_delivery_note,
}

# Per-category structured-field extractor. Categories not listed fall back to
# storing the raw recognised lines only.
_EXTRACTORS = {
    DocumentCategory.registration_card: extractors.extract_carte_grise,
    DocumentCategory.id_doc: extractors.extract_national_id,
    DocumentCategory.invoice: extractors.extract_invoice,
    DocumentCategory.supplier_invoice: extractors.extract_supplier_invoice,
    DocumentCategory.service_invoice: extractors.extract_service_invoice,
    DocumentCategory.supplier_delivery_note: extractors.extract_bon_de_livraison,
}


def _threshold_for(field: str, cfg) -> float:
    """Return the confidence threshold configured for a given field name."""
    if field == "immatriculation":
        return cfg.cfg_ocr_confidence_threshold_immatriculation
    if field == "vin":
        return cfg.cfg_ocr_confidence_threshold_vin
    if field in ("nom", "prenom", "proprietaire"):
        return cfg.cfg_ocr_confidence_threshold_nom
    if field == "numero_cin":
        return cfg.cfg_ocr_confidence_threshold_cin
    if "date" in field:
        return cfg.cfg_ocr_confidence_threshold_date
    return cfg.cfg_ocr_confidence_threshold_default


def _build_structured(
    raw_result: RawOcrResult, category: DocumentCategory, cfg
) -> tuple[dict[str, Any], dict[str, float], bool]:
    """Run the category extractor and merge with raw lines.

    Returns ``(structured_fields, confidence_scores, needs_review)``. A field is
    flagged for review when its confidence is below the configured threshold.
    """
    structured: dict[str, Any] = {}
    scores: dict[str, float] = {}

    extractor = _EXTRACTORS.get(category)
    extracted: FieldMap = extractor(raw_result) if extractor else {}

    needs_review = False
    for field, (value, conf) in extracted.items():
        structured[field] = value
        scores[field] = conf
        if conf < _threshold_for(field, cfg):
            needs_review = True

    # Always keep the raw recognised lines so the reviewer sees the full text.
    boxes: dict[str, list[int]] = {}
    for i, line in enumerate(raw_result.lines):
        key = f"ligne_{i + 1}"
        structured[key] = line.text
        scores[key] = line.confidence
        if line.box:
            boxes[key] = line.box

    # Layout metadata (image dims + per-line boxes) powers the preview highlight.
    # Stored under a reserved "__"-prefixed key the frontend filters out of fields.
    if raw_result.width and raw_result.height:
        structured["__layout__"] = {
            "width": raw_result.width,
            "height": raw_result.height,
            "boxes": boxes,
        }

    return structured, scores, needs_review


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def enqueue_ocr(db: AsyncSession, *, document_id: int) -> OcrExtraction:
    """Create a pending OCR extraction row for a document."""
    extraction = await ocr_repo.create(db, document_id=document_id)
    logger.info("ocr_enqueued", extraction_id=extraction.id, document_id=document_id)
    return extraction


async def process_ocr_job(db: AsyncSession, *, extraction_id: int) -> OcrExtraction:
    """
    Download the document from S3, run PaddleOCR, extract structured fields,
    evaluate confidence thresholds, and persist results.

    Status transitions:
        pending → processing → completed | needs_review | failed
    """
    extraction = await ocr_repo.get_by_id(db, extraction_id=extraction_id)
    if extraction is None:
        raise OcrNotFoundError(f"OcrExtraction {extraction_id} not found")

    # Mark as processing
    await ocr_repo.update_status(db, extraction_id=extraction_id, status=OcrStatus.processing)

    try:
        document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
        if document is None:
            raise OcrDocumentMissingError(f"Document {extraction.document_id} not found")

        cfg = get_settings()
        image_bytes = await doc_storage.download_object(
            bucket=cfg.s3_bucket_documents, key=document.storage_key
        )

        engine = get_ocr_engine()
        raw_result = await engine.run_ocr(image_bytes)

        # Run the category-specific extractor and merge with raw recognised lines.
        structured, scores, needs_review = _build_structured(
            raw_result, document.category, cfg
        )

        # For supplier_delivery_note documents that are linked to a purchase order,
        # inject the PO reference number as reference_commande upfront so it is
        # persisted in structured_fields from the very first extraction — no async
        # UI side-effect required to populate it.
        if (
            document.category == DocumentCategory.supplier_delivery_note
            and document.owner_entity_type == OwnerEntityType.purchase_order.value
            and document.owner_entity_id
            and "reference_commande" not in structured
        ):
            from app.modules.purchase_order.models import PurchaseOrder as _PO
            from sqlalchemy import select as _sel_po
            _po_res = await db.execute(
                _sel_po(_PO).where(
                    _PO.id == document.owner_entity_id,
                    _PO.deleted_at.is_(None),
                )
            )
            _po = _po_res.scalar_one_or_none()
            if _po and _po.doc_number:
                structured["reference_commande"] = _po.doc_number
                scores["reference_commande"] = 1.0  # authoritative — from the PO record

        if not structured:
            final_status = OcrStatus.completed
        else:
            final_status = OcrStatus.needs_review if needs_review else OcrStatus.completed

        await ocr_repo.update_status(
            db,
            extraction_id=extraction_id,
            status=final_status,
            raw_text=raw_result.full_text,
            structured_fields=structured,
            confidence_scores=scores,
            processed_at=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "ocr_processed",
            extraction_id=extraction_id,
            status=final_status,
            line_count=len(structured),
        )

    except Exception as exc:
        logger.error("ocr_failed", extraction_id=extraction_id, error=str(exc))
        await ocr_repo.update_status(
            db,
            extraction_id=extraction_id,
            status=OcrStatus.failed,
            processed_at=datetime.now(tz=timezone.utc),
        )
        raise

    refreshed = await ocr_repo.get_by_id(db, extraction_id=extraction_id)
    assert refreshed is not None
    return refreshed


async def confirm_fields(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    confirmed_fields: dict[str, str],
    reviewer_id: int,
) -> OcrExtraction:
    """
    Human confirms (or corrects) extracted field values.

    This is the ONLY place where OCR results are written to vehicle / customer
    tables. Confirmed fields are merged into the extraction row, all confirmed
    fields receive confidence = 1.0 (human-verified), and the owning entity
    (vehicle or customer) is patched based on the document category.
    """
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))

    if extraction.status not in (OcrStatus.completed, OcrStatus.needs_review):
        raise OcrInvalidStateError(
            f"Cannot confirm fields for extraction in status {extraction.status}"
        )

    # Merge confirmed values into structured_fields
    merged = dict(extraction.structured_fields or {})
    merged.update(confirmed_fields)

    # All confirmed fields get confidence = 1.0 (human-verified)
    merged_scores = dict(extraction.confidence_scores or {})
    for field in confirmed_fields:
        merged_scores[field] = 1.0

    await ocr_repo.update_status(
        db,
        extraction_id=extraction.id,
        status=OcrStatus.completed,
        structured_fields=merged,
        confidence_scores=merged_scores,
    )
    await ocr_repo.mark_reviewed(
        db,
        extraction_id=extraction.id,
        reviewed_by=reviewer_id,
        reviewed_at=datetime.now(tz=timezone.utc),
    )

    # Write confirmed fields back to the owning entity
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    if document is not None and document.owner_entity_id is not None:
        if (
            document.category == DocumentCategory.registration_card
            and document.owner_entity_type == OwnerEntityType.vehicle.value
        ):
            wrote = await vehicle_repo.patch_from_ocr(
                db,
                vehicle_id=document.owner_entity_id,
                garage_id=document.garage_id,
                fields=merged,
            )
            logger.info(
                "ocr_vehicle_writeback",
                vehicle_id=document.owner_entity_id,
                wrote=wrote,
                fields=list(merged.keys()),
            )
        elif (
            document.category == DocumentCategory.id_doc
            and document.owner_entity_type == OwnerEntityType.customer.value
        ):
            wrote = await customer_repo.patch_from_ocr(
                db,
                customer_id=document.owner_entity_id,
                garage_id=document.garage_id,
                fields=merged,
            )
            logger.info(
                "ocr_customer_writeback",
                customer_id=document.owner_entity_id,
                wrote=wrote,
                fields=list(merged.keys()),
            )

    refreshed = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    assert refreshed is not None
    return refreshed


def _parse_fr_date(value: str) -> str | None:
    """Convert a dd/mm/yyyy (or dd-mm-yy) string to an ISO date string."""
    if not value:
        return None
    m = re.match(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})", value.strip())
    if not m:
        return None
    day, month, year = m.group(1), m.group(2), m.group(3)
    if len(year) == 2:
        year = "20" + year
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return None


def _amount_to_cents(value: str) -> int | None:
    """Convert a normalised ``1234.56`` amount string to integer cents."""
    if not value:
        return None
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return None


def _build_invoice_prefill(fields: dict[str, Any], party_field: str) -> "InvoicePrefill":
    """Build an invoice-create prefill object from confirmed OCR fields."""
    from app.modules.ocr.schemas import IngestLine, InvoicePrefill

    suggested: list[IngestLine] = []
    raw_lines = fields.get("lignes")
    if raw_lines:
        try:
            for item in json.loads(raw_lines):
                suggested.append(IngestLine(**{k: (str(v) if v is not None else None) for k, v in item.items()}))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return InvoicePrefill(
        number=fields.get("numero_facture"),
        invoice_date=_parse_fr_date(fields.get("date_facture", "")),
        due_date=_parse_fr_date(fields.get("date_echeance", "")),
        party=fields.get(party_field),
        total_ht_cents=_amount_to_cents(fields.get("total_ht", "")),
        total_ttc_cents=_amount_to_cents(fields.get("total_ttc", "")),
        suggested_lines=suggested,
    )


def _si_lines_from_prefill(prefill: "InvoicePrefill") -> list[dict]:
    """Convert OCR-extracted suggested lines to standalone SI line dicts (no PO ref)."""
    lines = []
    for il in (prefill.suggested_lines or []):
        try:
            qty = max(1, int(float((il.quantity or "1").replace(",", ".")) or 1))
        except (TypeError, ValueError):
            qty = 1
        try:
            raw = (il.unit_price or "").replace(",", ".").strip()
            uph = max(0, int(round(float(raw) * 100))) if raw else 0
        except (TypeError, ValueError):
            uph = 0
        lth = qty * uph
        lttc = round(lth * 1.2)
        lines.append({
            "po_line_id": None,
            "description": il.description or "",
            "quantity": qty,
            "unit_price_ht": uph,
            "vat_rate": 20.0,
            "line_total_ht": lth,
            "line_total_ttc": lttc,
            "match_status": "ok",
            "po_quantity_ordered": 0,
            "po_quantity_received": 0,
            "po_unit_price_ht": uph,
        })
    return lines


async def ingest_extraction(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    confirmed_fields: dict[str, str],
    reviewer_id: int,
) -> "IngestionResult":
    """Confirm the reviewed fields, then route them to their destination.

    Reuses :func:`confirm_fields` (which persists the edits, marks the
    extraction reviewed, and performs the vehicle/customer write-back). For
    invoice categories it additionally returns a prefill payload so the caller
    can open the supplier-invoice / invoice create dialog.
    """
    from app.modules.ocr.schemas import IngestionResult

    extraction = await confirm_fields(
        db,
        extraction_public_id=extraction_public_id,
        confirmed_fields=confirmed_fields,
        reviewer_id=reviewer_id,
    )

    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    category = document.category if document is not None else None
    merged = extraction.structured_fields or {}

    if category == DocumentCategory.supplier_invoice:
        from datetime import date as _date
        from app.modules.supplier_invoice.service import create_supplier_invoice_from_ocr
        from app.modules.documents.models import OwnerEntityType

        prefill = _build_invoice_prefill(merged, "fournisseur")
        due = None
        if prefill.due_date:
            try:
                due = _date.fromisoformat(prefill.due_date)
            except ValueError:
                due = None
        si_lines = _si_lines_from_prefill(prefill)

        # --- Resolve supplier by name from confirmed fields ---
        supplier_id: int | None = None
        if prefill.party:
            from app.modules.supplier.models import Supplier as SupplierModel
            from sqlalchemy import select as _sa_sel, func as _sa_func
            sup_res = await db.execute(
                _sa_sel(SupplierModel).where(
                    SupplierModel.garage_id == document.garage_id,
                    _sa_func.lower(SupplierModel.name) == prefill.party.lower().strip(),
                    SupplierModel.deleted_at.is_(None),
                )
            )
            sup = sup_res.scalar_one_or_none()
            if sup:
                supplier_id = sup.id

        # --- If document is filed under a PO, link invoice + auto-receive ---
        po_db_id: int | None = None
        if (
            document is not None
            and document.owner_entity_type == OwnerEntityType.purchase_order.value
            and document.owner_entity_id
        ):
            from app.modules.purchase_order.models import PurchaseOrder
            from app.modules.purchase_order.service import receive_po
            from app.modules.parts.repository import PartRepository
            from sqlalchemy import select as _sa_sel2

            po_res = await db.execute(
                _sa_sel2(PurchaseOrder).where(
                    PurchaseOrder.id == document.owner_entity_id,
                    PurchaseOrder.garage_id == document.garage_id,
                    PurchaseOrder.deleted_at.is_(None),
                )
            )
            po = po_res.scalar_one_or_none()
            if po:
                po_db_id = po.id
                # Inherit supplier from PO if not already resolved.
                if not supplier_id:
                    supplier_id = po.supplier_id

                # For "Autre" PO lines (no part_id), find or create a catalogue
                # part so the reception can proceed.
                for po_line in po.lines:
                    if po_line.part_id is not None:
                        continue
                    label = (po_line.label or "").strip()
                    if not label:
                        continue
                    # Search inventory by name (case-insensitive).
                    from app.modules.parts.models import Part as PartModel
                    from sqlalchemy import func as _sa_func2
                    p_res = await db.execute(
                        _sa_sel2(PartModel).where(
                            PartModel.garage_id == document.garage_id,
                            _sa_func2.lower(PartModel.name) == label.lower(),
                            PartModel.deleted_at.is_(None),
                        )
                    )
                    part = p_res.scalar_one_or_none()
                    if not part:
                        # Auto-create a minimal catalogue part from the label.
                        import uuid as _uuid
                        part = PartModel(
                            public_id=_uuid.uuid4(),
                            garage_id=document.garage_id,
                            sku_code=label[:50].upper().replace(" ", "_"),
                            name=label,
                            unit_of_measure="unité",
                            purchase_price_minor=0,
                            selling_price_minor=0,
                        )
                        db.add(part)
                        await db.flush()
                    po_line.part_id = part.id
                await db.flush()

                # Auto-receive the PO — the invoice acts as the delivery note.
                recv_lines = [
                    {"line_id": ln.id, "quantity_received": ln.quantity_ordered}
                    for ln in po.lines
                    if ln.quantity_ordered > ln.quantity_received
                ]
                if recv_lines:
                    try:
                        po = await receive_po(
                            db,
                            document.garage_id,
                            str(po.public_id),
                            po.version,
                            recv_lines,
                            reviewer_id,
                        )
                        logger.info(
                            "supplier_invoice_ocr_auto_received_po",
                            po_public_id=str(po.public_id),
                            garage_id=document.garage_id,
                        )
                    except Exception as exc:
                        # Auto-reception is best-effort; don't block invoice creation.
                        logger.warning(
                            "supplier_invoice_ocr_auto_receive_failed",
                            error=str(exc),
                            garage_id=document.garage_id,
                        )

        si = await create_supplier_invoice_from_ocr(
            db,
            garage_id=document.garage_id,
            number=prefill.number or "(sans numéro)",
            total_ht=prefill.total_ht_cents or 0,
            total_ttc=prefill.total_ttc_cents or 0,
            supplier_id=supplier_id,
            purchase_order_id=po_db_id,
            lines=si_lines if si_lines else None,
            due_date=due,
            notes="Importé depuis l'OCR",
            created_by=reviewer_id,
        )
        # get_db does not auto-commit; persist the new invoice explicitly.
        await db.commit()
        # Store the created SI public_id in structured_fields so the OCR review
        # page can load live SI lines on future revisits instead of the OCR snapshot.
        linked_fields = {**extraction.structured_fields, "__linked_si_id__": str(si.public_id)}
        from app.modules.ocr import repository as _ocr_repo
        from app.modules.ocr.models import OcrStatus as _OcrStatus
        await _ocr_repo.update_status(
            db,
            extraction_id=extraction.id,
            status=_OcrStatus.completed,
            structured_fields=linked_fields,
        )
        await db.commit()
        return IngestionResult(
            target="supplier_invoice",
            prefill=prefill,
            created_id=str(si.public_id),
        )

    if category == DocumentCategory.service_invoice:
        from datetime import date as _date2
        from app.modules.supplier_invoice.service import create_supplier_invoice_from_ocr as _create_si

        prefill = _build_invoice_prefill(merged, "fournisseur")
        due = None
        if prefill.due_date:
            try:
                due = _date2.fromisoformat(prefill.due_date)
            except ValueError:
                due = None
        si_lines = _si_lines_from_prefill(prefill)

        # Resolve supplier by name — look up or create if document is linked to a supplier.
        supplier_id = None
        if prefill.party:
            from app.modules.supplier.models import Supplier as _SupModel
            from sqlalchemy import select as _sel3, func as _func3
            sup_res = await db.execute(
                _sel3(_SupModel).where(
                    _SupModel.garage_id == document.garage_id,
                    _func3.lower(_SupModel.name) == prefill.party.lower().strip(),
                    _SupModel.deleted_at.is_(None),
                )
            )
            sup = sup_res.scalar_one_or_none()
            if sup:
                supplier_id = sup.id

        # If document is filed under a supplier, inherit that link.
        if not supplier_id and document.owner_entity_type == OwnerEntityType.supplier.value and document.owner_entity_id:
            supplier_id = document.owner_entity_id

        si = await _create_si(
            db,
            garage_id=document.garage_id,
            number=prefill.number or "(sans numéro)",
            total_ht=prefill.total_ht_cents or 0,
            total_ttc=prefill.total_ttc_cents or 0,
            supplier_id=supplier_id,
            purchase_order_id=None,       # service invoices are never PO-linked
            invoice_type="services",
            lines=si_lines if si_lines else None,
            due_date=due,
            notes="Facture de service — importée depuis l'OCR",
            created_by=reviewer_id,
        )
        await db.commit()
        logger.info(
            "service_invoice_created_from_ocr",
            si_public_id=str(si.public_id),
            garage_id=document.garage_id,
        )

        # Enrich the linked supplier with email / phone extracted from the invoice
        # if those fields are currently blank (safe — only fills empty columns).
        if supplier_id:
            from app.modules.supplier.models import Supplier as _SupEnrich
            from sqlalchemy import select as _sel_enrich
            enrich_res = await db.execute(
                _sel_enrich(_SupEnrich).where(_SupEnrich.id == supplier_id)
            )
            sup_enrich = enrich_res.scalar_one_or_none()
            if sup_enrich:
                changed = False
                ocr_email = merged.get("email", (None,))[0]
                ocr_phone = merged.get("telephone", (None,))[0]
                if ocr_email and not sup_enrich.email:
                    sup_enrich.email = ocr_email
                    changed = True
                if ocr_phone and not sup_enrich.phone:
                    sup_enrich.phone = ocr_phone
                    changed = True
                if changed:
                    await db.commit()
                    logger.info(
                        "supplier_contact_enriched_from_service_invoice",
                        supplier_id=supplier_id,
                        email=ocr_email,
                        phone=ocr_phone,
                    )

        # Store the created SI public_id in structured_fields so the OCR review
        # page can load live SI lines on future revisits instead of the OCR snapshot.
        linked_fields = {**extraction.structured_fields, "__linked_si_id__": str(si.public_id)}
        from app.modules.ocr import repository as _ocr_repo2
        from app.modules.ocr.models import OcrStatus as _OcrStatus2
        await _ocr_repo2.update_status(
            db,
            extraction_id=extraction.id,
            status=_OcrStatus2.completed,
            structured_fields=linked_fields,
        )
        await db.commit()

        return IngestionResult(
            target="supplier_invoice",   # reuses the supplier_invoice target → navigates to services page
            prefill=prefill,
            created_id=str(si.public_id),
        )

    if category == DocumentCategory.invoice:
        from app.modules.invoice.service import create_invoice_from_ocr

        prefill = _build_invoice_prefill(merged, "client")
        ttc = prefill.total_ttc_cents or 0
        ht = prefill.total_ht_cents or 0
        invoice = await create_invoice_from_ocr(
            db,
            garage_id=document.garage_id,
            user_id=reviewer_id,
            doc_number=prefill.number,
            subtotal_minor=ht,
            vat_minor=max(ttc - ht, 0),
            total_minor=ttc,
            notes="Importé depuis l'OCR",
        )
        return IngestionResult(
            target="invoice", prefill=prefill, created_id=invoice.public_id
        )
    if category == DocumentCategory.registration_card:
        return IngestionResult(target="vehicle")
    if category == DocumentCategory.id_doc:
        return IngestionResult(target="customer")
    return IngestionResult(target="none")


async def ocr_region(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    box: tuple[int, int, int, int],
    page: int = 0,
) -> str:
    """Run OCR on a sub-region of the extraction's source document."""
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    if document is None:
        raise OcrDocumentMissingError(str(extraction.document_id))
    cfg = get_settings()
    data = await doc_storage.download_object(
        bucket=cfg.s3_bucket_documents, key=document.storage_key
    )
    engine = get_ocr_engine()
    return await engine.run_ocr_region(data, box, max(0, page))


async def get_page_image(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    page: int = 0,
) -> tuple[bytes, int]:
    """Return ``(png_bytes, total_pages)`` for the given 0-based page.

    The source document is downloaded once; multi-page PDFs expose every page
    (capped at the engine's MAX_PDF_PAGES) so the preview can paginate.
    """
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))
    document = await doc_repo.get_by_id(db, document_id=extraction.document_id)
    if document is None:
        raise OcrDocumentMissingError(str(extraction.document_id))
    cfg = get_settings()
    data = await doc_storage.download_object(
        bucket=cfg.s3_bucket_documents, key=document.storage_key
    )
    engine = get_ocr_engine()
    total = await engine.page_count(data)
    image = await engine.render_page_png(data, max(0, page))
    return image, total


async def suggest_field(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    field_key: str,
) -> "str | None":
    """Auto-match a field with the best candidate from the recognised text."""
    from app.modules.ocr.engine import OcrLine

    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))

    sf = extraction.structured_fields or {}
    layout = sf.get("__layout__", {}) or {}
    boxes = layout.get("boxes", {}) or {}
    scores = extraction.confidence_scores or {}
    # Rebuild the recognised lines (ligne_*) with boxes for layout-aware matching.
    lines: list[OcrLine] = []
    for key, value in sf.items():
        if not key.startswith("ligne_"):
            continue
        lines.append(
            OcrLine(
                text=str(value),
                confidence=float(scores.get(key, 0.0) or 0.0),
                box=boxes.get(key),
            )
        )
    result = RawOcrResult(lines=lines, full_text="\n".join(ln.text for ln in lines))
    return extractors.suggest_field(result, field_key)


async def reject_extraction(
    db: AsyncSession,
    *,
    extraction_public_id: uuid.UUID,
    reviewer_id: int,
) -> OcrExtraction:
    """Mark an extraction as failed (human rejected the result)."""
    extraction = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    if extraction is None:
        raise OcrNotFoundError(str(extraction_public_id))

    await ocr_repo.update_status(
        db, extraction_id=extraction.id, status=OcrStatus.failed
    )
    await ocr_repo.mark_reviewed(
        db,
        extraction_id=extraction.id,
        reviewed_by=reviewer_id,
        reviewed_at=datetime.now(tz=timezone.utc),
    )

    refreshed = await ocr_repo.get_by_public_id(db, public_id=extraction_public_id)
    assert refreshed is not None
    return refreshed


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OcrNotFoundError(Exception):
    pass


class OcrDocumentMissingError(Exception):
    pass


class OcrInvalidStateError(Exception):
    pass
