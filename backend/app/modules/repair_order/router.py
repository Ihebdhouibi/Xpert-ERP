"""Repair Order module HTTP endpoints."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.models import AppUser
from app.modules.repair_order.models import ROStatus
from app.modules.repair_order.repository import RepairOrderRepository
from app.modules.repair_order.schemas import (
    RepairOrderCreateRequest,
    RepairOrderDetail,
    RepairOrderSummary,
    RepairOrderUpdateRequest,
    ROLaborLineCreateRequest,
    ROPartLineCreateRequest,
    StatusTransitionRequest,
)
from app.modules.repair_order.service import (
    InvalidStatusTransitionError,
    OptimisticLockError,
    RepairOrderNotFoundError,
    RepairOrderService,
)
from app.modules.rbac.dependencies import AuthUser, require_permission, require_role

router = APIRouter(prefix="/repair-orders", tags=["repair-orders"])


async def _resolve_user_id(db: AsyncSession, public_id: str) -> Optional[int]:
    """Resolve JWT subject (public_id) → internal app_user.id for audit."""
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(AppUser.id).where(AppUser.public_id == uid))
    row = result.first()
    return row[0] if row else None


async def _get_detail(db: AsyncSession, garage_id: int, public_id: str, include_deleted: bool = False) -> RepairOrderDetail:
    """Fetch a repair order with all relationships eagerly loaded and return as detail schema."""
    ro = await RepairOrderRepository.get_by_public_id(
        db, garage_id, public_id, include_deleted=include_deleted, load_relationships=True
    )
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")
    return RepairOrderDetail.model_validate(ro)


@router.get(
    "",
    response_model=dict,
    dependencies=[require_permission("repair_order.read")],
)
async def list_repair_orders(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    status: Optional[ROStatus] = None,
    customer_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """List repair orders with optional filters and pagination."""
    rows, total = await RepairOrderRepository.list(
        db,
        garage_id=user.garage_id,
        status=status,
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [RepairOrderSummary.model_validate(ro) for ro in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{public_id}",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.read")],
)
async def get_repair_order(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Get repair order detail by public ID."""
    return await _get_detail(db, user.garage_id, public_id)


@router.post(
    "",
    response_model=RepairOrderDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("repair_order.create")],
)
async def create_repair_order(
    body: RepairOrderCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Create a new repair order."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        ro = await RepairOrderService.create_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            customer_id=body.customer_id,
            vehicle_id=body.vehicle_id,
            description=body.description,
            priority=body.priority,
            estimated_cost_minor=body.estimated_cost_minor,
            estimated_cost_currency=body.estimated_cost_currency,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, str(ro.public_id))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/{public_id}",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.update")],
)
async def update_repair_order(
    public_id: str,
    body: RepairOrderUpdateRequest,
    user: AuthUser,
    version: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Update repair order fields (optimistic locking via version query param)."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.update_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
            submitted_version=version,
            description=body.description,
            priority=body.priority,
            estimated_cost_minor=body.estimated_cost_minor,
            estimated_cost_currency=body.estimated_cost_currency,
            notes=body.notes,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, public_id)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except OptimisticLockError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_version",
                "current_version": e.current_version,
                "submitted_version": e.submitted_version,
            },
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("repair_order.delete")],
)
async def delete_repair_order(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete a repair order."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.soft_delete_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
        )
        await db.commit()
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{public_id}/restore",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.delete"), require_role("admin")],
)
async def restore_repair_order(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Restore a soft-deleted repair order (admin only)."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.restore_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, public_id, include_deleted=True)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{public_id}/status-transition",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.transition")],
)
async def transition_status(
    public_id: str,
    body: StatusTransitionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Transition repair order to a new status."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.transition_status(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
            new_status=body.new_status,
            reason=body.reason,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, public_id)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_transition",
                "from_status": e.from_status.value,
                "to_status": e.to_status.value,
            },
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{public_id}/labor-lines",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.update")],
)
async def add_labor_line(
    public_id: str,
    body: ROLaborLineCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Add a labor line to a repair order."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.add_labor_line(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
            labor_type=body.labor_type,
            duration_minutes=body.duration_minutes,
            rate_minor=body.rate_minor,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, public_id)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{public_id}/part-lines",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.update")],
)
async def add_part_line(
    public_id: str,
    body: ROPartLineCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Add a part line to a repair order."""
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.add_part_line(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
            part_name=body.part_name,
            quantity=body.quantity,
            unit_cost_minor=body.unit_cost_minor,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, public_id)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
