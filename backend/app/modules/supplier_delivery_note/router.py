from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi import status as http_status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.modules.purchase_order.service import (
    POInvalidTransitionError,
    POVersionConflictError,
)
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.supplier_delivery_note import service
from app.modules.supplier_delivery_note.service import (
    AutreLinePartMissingError,
    DuplicateBLNumberError,
    PONotLinkedError,
    SDNError,
)

router = APIRouter(tags=["supplier-delivery-notes"])
logger = get_logger("supplier_delivery_note.router")


class SDNLineInput(BaseModel):
    po_line_id: int
    quantity_received: int = Field(..., ge=0)
    # Assign a catalogue part to an "Autre" PO line (the swap).
    part_public_id: Optional[str] = None
    # BL-captured fields (recorded on the delivery-note line). Prices in minor units.
    code: Optional[str] = None
    designation: Optional[str] = None
    pu_brut: Optional[int] = None
    pu_net: Optional[int] = None
    montant_ht: Optional[int] = None


class SDNCreateRequest(BaseModel):
    extraction_id: uuid.UUID
    bl_number: Optional[str] = None
    bl_date: Optional[date] = None
    notes: Optional[str] = None
    allow_duplicate_bl_number: bool = False
    # Email read from the BL — associated to the supplier profile if it has none.
    supplier_email: Optional[str] = None
    lines: list[SDNLineInput] = Field(..., min_length=1)


class SDNResponse(BaseModel):
    id: str
    bl_number: Optional[str] = None
    bl_date: Optional[date] = None
    status: str
    has_discrepancy: bool
    created_at: datetime


@router.get(
    "/supplier-delivery-notes/po-for-extraction/{extraction_id}",
    dependencies=[require_permission("purchase_order.read")],
    summary="Resolve the purchase order linked to a BL's OCR extraction",
)
async def po_for_extraction(
    extraction_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        po = await service.get_po_for_extraction(
            db, garage_id=user.garage_id, extraction_public_id=extraction_id
        )
    except (PONotLinkedError, SDNError) as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"purchase_order_public_id": str(po.public_id), "supplier_id": po.supplier_id}


@router.post(
    "/supplier-delivery-notes",
    status_code=http_status.HTTP_201_CREATED,
    response_model=SDNResponse,
    dependencies=[require_permission("purchase_order.reception.record")],
    summary="Create a BL and perform the goods reception against its purchase order",
)
async def create_supplier_delivery_note(
    body: SDNCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SDNResponse:
    try:
        sdn = await service.create_delivery_note(
            db,
            garage_id=user.garage_id,
            user_id=user.user_id,
            extraction_public_id=body.extraction_id,
            bl_number=body.bl_number,
            bl_date=body.bl_date,
            notes=body.notes,
            lines=[ln.model_dump() for ln in body.lines],
            allow_duplicate_bl_number=body.allow_duplicate_bl_number,
            supplier_email=body.supplier_email,
        )
        await db.commit()
        await db.refresh(sdn)
    except DuplicateBLNumberError as e:
        # Sentinel detail so the client can offer an "override" re-submit.
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"DUPLICATE_BL_NUMBER:{e.bl_number}",
        )
    except AutreLinePartMissingError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ligne « Autre » sans pièce définie (ligne {e}).",
        )
    except (PONotLinkedError, POVersionConflictError, POInvalidTransitionError, SDNError) as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    return SDNResponse(
        id=str(sdn.public_id),
        bl_number=sdn.bl_number,
        bl_date=sdn.bl_date,
        status=sdn.status,
        has_discrepancy=sdn.has_discrepancy,
        created_at=sdn.created_at,
    )
