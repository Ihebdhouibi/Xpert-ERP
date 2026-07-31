"""Stock movement and level endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.parts.models import Part
from app.modules.parts.repository import PartRepository
from app.modules.parts.stock_models import LowStockAlert, LowStockAlertStatus, StockLevel, StockMovement, StockMovementType
from app.modules.parts.stock_repository import StockRepository
from app.modules.parts.stock_service import (
    InvalidMovementError,
    NegativeStockError,
    record_movement,
    release_all_for_ref,
    release_for_ref,
    reserve_for_ref,
)
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.core.logging import get_logger

router = APIRouter(tags=["stock"])
logger = get_logger("parts.stock_router")


# ---------------------------------------------------------------------------
# Schemas (inline — small surface area)
# ---------------------------------------------------------------------------

class StockMovementRequest(BaseModel):
    type: StockMovementType
    quantity: int = Field(..., description="Positive for in/out/reservation/release; signed for adjustment")
    unit_cost_minor: Optional[StrictInt] = Field(None, ge=0, description="Required for 'in' movements")
    ref_type: Optional[str] = Field(None, max_length=50)
    ref_id: Optional[str] = Field(None, max_length=100)
    reason: Optional[str] = None


class ReserveRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    ref_type: str = Field(..., max_length=50)
    ref_id: str = Field(..., max_length=100)
    reason: Optional[str] = None


class ReleaseRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    ref_type: str = Field(..., max_length=50)
    ref_id: str = Field(..., max_length=100)
    reason: Optional[str] = None


class StockLevelResponse(BaseModel):
    part_id: int
    part_public_id: Optional[str] = None
    part_name: Optional[str] = None
    sku_code: Optional[str] = None
    garage_id: int
    on_hand: int
    reserved: int
    available: int
    avg_cost_minor: int
    updated_at: str

    @classmethod
    def from_orm(cls, level: StockLevel, part: Optional[Part] = None) -> StockLevelResponse:
        return cls(
            part_id=level.part_id,
            part_public_id=str(part.public_id) if part else None,
            part_name=part.name if part else None,
            sku_code=part.sku_code if part else None,
            garage_id=level.garage_id,
            on_hand=level.on_hand,
            reserved=level.reserved,
            available=level.on_hand - level.reserved,
            avg_cost_minor=level.avg_cost_minor,
            updated_at=level.updated_at.isoformat(),
        )


class StockMovementResponse(BaseModel):
    id: int
    part_id: int
    part_name: Optional[str] = None
    sku_code: Optional[str] = None
    garage_id: int
    type: str
    quantity: int
    unit_cost_minor: Optional[int]
    ref_type: Optional[str]
    ref_id: Optional[str]
    reason: Optional[str]
    created_by_user_id: Optional[int]
    created_at: str

    @classmethod
    def from_orm(cls, mv: StockMovement, part: Optional[Part] = None) -> StockMovementResponse:
        return cls(
            id=mv.id,
            part_id=mv.part_id,
            part_name=part.name if part else None,
            sku_code=part.sku_code if part else None,
            garage_id=mv.garage_id,
            type=mv.type.value,
            quantity=mv.quantity,
            unit_cost_minor=mv.unit_cost_minor,
            ref_type=mv.ref_type,
            ref_id=mv.ref_id,
            reason=mv.reason,
            created_by_user_id=mv.created_by_user_id,
            created_at=mv.created_at.isoformat(),
        )


class LowStockAlertResponse(BaseModel):
    id: int
    part_id: int
    part_name: Optional[str] = None
    sku_code: Optional[str] = None
    garage_id: int
    on_hand: int
    threshold: int
    suggested_supplier_id: Optional[int]
    suggested_reorder_quantity: Optional[int]
    status: str
    created_at: str

    @classmethod
    def from_orm(cls, alert: LowStockAlert, part: Optional[Part] = None) -> LowStockAlertResponse:
        return cls(
            id=alert.id,
            part_id=alert.part_id,
            part_name=part.name if part else None,
            sku_code=part.sku_code if part else None,
            garage_id=alert.garage_id,
            on_hand=alert.on_hand,
            threshold=alert.threshold,
            suggested_supplier_id=alert.suggested_supplier_id,
            suggested_reorder_quantity=alert.suggested_reorder_quantity,
            status=alert.status.value,
            created_at=alert.created_at.isoformat(),
        )


class ValuationItemResponse(BaseModel):
    part_id: int
    part_name: Optional[str] = None
    sku_code: Optional[str] = None
    on_hand: int
    avg_cost_minor: int
    total_value_minor: int


class ValuationReportResponse(BaseModel):
    items: list[ValuationItemResponse]
    total_inventory_value_minor: int


# ---------------------------------------------------------------------------
# Part stock endpoints (nested under /parts/{public_id}/stock)
# ---------------------------------------------------------------------------

async def _resolve_part_id(
    db: AsyncSession, garage_id: int, public_id: str
) -> int:
    part = await PartRepository.get_by_public_id(db, garage_id, public_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return part.id


@router.get(
    "/parts/{public_id}/stock",
    response_model=StockLevelResponse,
    dependencies=[require_permission("part.read")],
)
async def get_stock_level(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> StockLevelResponse:
    part = await PartRepository.get_by_public_id(db, user.garage_id, public_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    level = await StockRepository.get_level(db, user.garage_id, part.id)
    if level is None:
        from datetime import datetime, timezone
        level = StockLevel(
            garage_id=user.garage_id,
            part_id=part.id,
            on_hand=0,
            reserved=0,
            avg_cost_minor=0,
            updated_at=datetime.now(timezone.utc),
        )
    return StockLevelResponse.from_orm(level, part)


@router.get(
    "/parts/{public_id}/stock/movements",
    response_model=list[StockMovementResponse],
    dependencies=[require_permission("part.read")],
)
async def list_part_movements(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[StockMovementResponse]:
    part_id = await _resolve_part_id(db, user.garage_id, public_id)
    movements = await StockRepository.list_movements(
        db, user.garage_id, part_id=part_id, limit=limit, offset=offset
    )
    return [StockMovementResponse.from_orm(m) for m in movements]


@router.post(
    "/parts/{public_id}/stock/movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("part.update")],
)
async def create_stock_movement(
    public_id: str,
    body: StockMovementRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> StockMovementResponse:
    settings = get_settings()
    part_id = await _resolve_part_id(db, user.garage_id, public_id)
    try:
        # Stock increases must be traceable to a purchase order — this
        # ad-hoc endpoint is not the reception flow (see
        # purchase_order.service.receive_po, which handles PO-linked
        # receipts atomically). "out"/"adjustment" movements are unaffected.
        if body.type == StockMovementType.in_ and (
            body.ref_type != "purchase_order" or not body.ref_id
        ):
            raise InvalidMovementError(
                "Un mouvement d'entrée doit être lié à un bon de commande "
                "(réceptionnez-le depuis le bon de commande)."
            )
        mv = await record_movement(
            db,
            garage_id=user.garage_id,
            part_id=part_id,
            movement_type=body.type,
            quantity=body.quantity,
            unit_cost_minor=body.unit_cost_minor,
            ref_type=body.ref_type,
            ref_id=body.ref_id,
            reason=body.reason,
            created_by_user_id=user.user_id,
            allow_negative=settings.cfg_allow_negative_stock,
        )
        await db.commit()
        await db.refresh(mv)
        return StockMovementResponse.from_orm(mv)
    except NegativeStockError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "negative_stock",
                "available": e.available,
                "requested": e.requested,
            },
        )
    except InvalidMovementError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/parts/{public_id}/stock/reserve",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("part.update")],
)
async def reserve_stock(
    public_id: str,
    body: ReserveRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> StockMovementResponse:
    part_id = await _resolve_part_id(db, user.garage_id, public_id)
    try:
        mv = await reserve_for_ref(
            db,
            garage_id=user.garage_id,
            part_id=part_id,
            quantity=body.quantity,
            ref_type=body.ref_type,
            ref_id=body.ref_id,
            reason=body.reason,
            created_by_user_id=user.user_id,
        )
        await db.commit()
        await db.refresh(mv)
        return StockMovementResponse.from_orm(mv)
    except InvalidMovementError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/parts/{public_id}/stock/release",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("part.update")],
)
async def release_stock(
    public_id: str,
    body: ReleaseRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> StockMovementResponse:
    part_id = await _resolve_part_id(db, user.garage_id, public_id)
    try:
        mv = await release_for_ref(
            db,
            garage_id=user.garage_id,
            part_id=part_id,
            quantity=body.quantity,
            ref_type=body.ref_type,
            ref_id=body.ref_id,
            reason=body.reason,
            created_by_user_id=user.user_id,
        )
        await db.commit()
        await db.refresh(mv)
        return StockMovementResponse.from_orm(mv)
    except InvalidMovementError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Garage-wide stock endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/stock/levels",
    response_model=list[StockLevelResponse],
    dependencies=[require_permission("part.read")],
)
async def list_stock_levels(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[StockLevelResponse]:
    from sqlalchemy import select
    levels = await StockRepository.list_levels(db, user.garage_id)
    # Batch-fetch part info
    part_ids = [l.part_id for l in levels]
    parts_map: dict[int, Part] = {}
    if part_ids:
        result = await db.execute(
            select(Part).where(Part.id.in_(part_ids), Part.garage_id == user.garage_id)
        )
        for p in result.scalars().all():
            parts_map[p.id] = p
    return [StockLevelResponse.from_orm(l, parts_map.get(l.part_id)) for l in levels]


@router.get(
    "/stock/movements",
    response_model=list[StockMovementResponse],
    dependencies=[require_permission("part.read")],
)
async def list_all_movements(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[StockMovementResponse]:
    from sqlalchemy import select
    movements = await StockRepository.list_movements(
        db, user.garage_id,
        ref_type=ref_type,
        ref_id=ref_id,
        limit=limit,
        offset=offset,
    )
    part_ids = list({m.part_id for m in movements})
    parts_map: dict[int, Part] = {}
    if part_ids:
        result = await db.execute(
            select(Part).where(Part.id.in_(part_ids), Part.garage_id == user.garage_id)
        )
        for p in result.scalars().all():
            parts_map[p.id] = p
    return [StockMovementResponse.from_orm(m, parts_map.get(m.part_id)) for m in movements]


@router.get(
    "/stock/alerts",
    response_model=list[LowStockAlertResponse],
    dependencies=[require_permission("part.read")],
)
async def list_alerts(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = None,
    include_resolved: bool = False,
) -> list[LowStockAlertResponse]:
    from sqlalchemy import select
    alerts = await StockRepository.list_alerts(
        db, user.garage_id, status=status, include_resolved=include_resolved
    )
    part_ids = list({a.part_id for a in alerts})
    parts_map: dict[int, Part] = {}
    if part_ids:
        result = await db.execute(
            select(Part).where(Part.id.in_(part_ids), Part.garage_id == user.garage_id)
        )
        for p in result.scalars().all():
            parts_map[p.id] = p
    return [LowStockAlertResponse.from_orm(a, parts_map.get(a.part_id)) for a in alerts]


@router.post(
    "/stock/alerts/{alert_id}/acknowledge",
    response_model=LowStockAlertResponse,
    dependencies=[require_permission("part.update")],
)
async def acknowledge_alert(
    alert_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> LowStockAlertResponse:
    alert = await StockRepository.get_alert(db, user.garage_id, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status == LowStockAlertStatus.resolved:
        raise HTTPException(status_code=409, detail="Alert already resolved")
    alert = await StockRepository.acknowledge_alert(db, alert)
    await db.commit()
    return LowStockAlertResponse.from_orm(alert)


@router.post(
    "/stock/alerts/{alert_id}/resolve",
    response_model=LowStockAlertResponse,
    dependencies=[require_permission("part.update")],
)
async def resolve_alert(
    alert_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> LowStockAlertResponse:
    alert = await StockRepository.get_alert(db, user.garage_id, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert = await StockRepository.resolve_alert(db, alert)
    await db.commit()
    return LowStockAlertResponse.from_orm(alert)


@router.get(
    "/stock/valuation",
    response_model=ValuationReportResponse,
    dependencies=[require_permission("part.read")],
)
async def get_stock_valuation(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> ValuationReportResponse:
    """Return current inventory valuation: per-part on_hand × avg_cost."""
    from sqlalchemy import select
    levels = await StockRepository.list_levels(db, user.garage_id)
    part_ids = [l.part_id for l in levels]
    parts_map: dict[int, Part] = {}
    if part_ids:
        result = await db.execute(
            select(Part).where(Part.id.in_(part_ids), Part.garage_id == user.garage_id)
        )
        for p in result.scalars().all():
            parts_map[p.id] = p
    items = [
        ValuationItemResponse(
            part_id=level.part_id,
            part_name=parts_map[level.part_id].name if level.part_id in parts_map else None,
            sku_code=parts_map[level.part_id].sku_code if level.part_id in parts_map else None,
            on_hand=level.on_hand,
            avg_cost_minor=level.avg_cost_minor,
            total_value_minor=level.on_hand * level.avg_cost_minor,
        )
        for level in levels
    ]
    return ValuationReportResponse(
        items=items,
        total_inventory_value_minor=sum(i.total_value_minor for i in items),
    )
