"""Stock movement and level endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.parts.repository import PartRepository
from app.modules.parts.stock_models import LowStockAlert, StockLevel, StockMovement, StockMovementType
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

router = APIRouter(tags=["stock"])


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
    garage_id: int
    on_hand: int
    reserved: int
    available: int
    avg_cost_minor: int
    updated_at: str

    @classmethod
    def from_orm(cls, level: StockLevel) -> StockLevelResponse:
        return cls(
            part_id=level.part_id,
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
    def from_orm(cls, mv: StockMovement) -> StockMovementResponse:
        return cls(
            id=mv.id,
            part_id=mv.part_id,
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
    garage_id: int
    on_hand: int
    threshold: int
    acknowledged: bool
    created_at: str

    @classmethod
    def from_orm(cls, alert: LowStockAlert) -> LowStockAlertResponse:
        return cls(
            id=alert.id,
            part_id=alert.part_id,
            garage_id=alert.garage_id,
            on_hand=alert.on_hand,
            threshold=alert.threshold,
            acknowledged=alert.acknowledged,
            created_at=alert.created_at.isoformat(),
        )


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
    part_id = await _resolve_part_id(db, user.garage_id, public_id)
    level = await StockRepository.get_level(db, user.garage_id, part_id)
    if level is None:
        # Return zeroed level for parts with no movements yet
        from datetime import datetime, timezone
        level = StockLevel(
            garage_id=user.garage_id,
            part_id=part_id,
            on_hand=0,
            reserved=0,
            avg_cost_minor=0,
            updated_at=datetime.now(timezone.utc),
        )
    return StockLevelResponse.from_orm(level)


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
    levels = await StockRepository.list_levels(db, user.garage_id)
    return [StockLevelResponse.from_orm(l) for l in levels]


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
    movements = await StockRepository.list_movements(
        db, user.garage_id,
        ref_type=ref_type,
        ref_id=ref_id,
        limit=limit,
        offset=offset,
    )
    return [StockMovementResponse.from_orm(m) for m in movements]


@router.get(
    "/stock/alerts",
    response_model=list[LowStockAlertResponse],
    dependencies=[require_permission("part.read")],
)
async def list_alerts(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    include_acknowledged: bool = False,
) -> list[LowStockAlertResponse]:
    alerts = await StockRepository.list_alerts(
        db, user.garage_id, include_acknowledged=include_acknowledged
    )
    return [LowStockAlertResponse.from_orm(a) for a in alerts]


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
    alert = await StockRepository.acknowledge_alert(db, alert)
    await db.commit()
    return LowStockAlertResponse.from_orm(alert)
