from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
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
from app.modules.rbac.dependencies import require_permission

router = APIRouter(prefix="/repair-orders", tags=["repair-orders"])


@router.get("", response_model=dict)
async def list_repair_orders(
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
    status: ROStatus | None = None,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List repair orders with optional filters and pagination."""
    await require_permission(db, user.id, "repair_order.read")

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


@router.get("/{public_id}", response_model=RepairOrderDetail)
async def get_repair_order(
    public_id: str,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Get repair order detail by public ID."""
    await require_permission(db, user.id, "repair_order.read")

    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    return RepairOrderDetail.model_validate(ro)


@router.post("", response_model=RepairOrderDetail, status_code=status.HTTP_201_CREATED)
async def create_repair_order(
    body: RepairOrderCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Create a new repair order."""
    await require_permission(db, user.id, "repair_order.create")

    try:
        ro = await RepairOrderService.create_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=user.id,
            customer_id=body.customer_id,
            vehicle_id=body.vehicle_id,
            description=body.description,
            priority=body.priority,
            estimated_cost_minor=body.estimated_cost_minor,
            estimated_cost_currency=body.estimated_cost_currency,
        )
        await db.commit()
        await db.refresh(ro)
        return RepairOrderDetail.model_validate(ro)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{public_id}", response_model=RepairOrderDetail)
async def update_repair_order(
    public_id: str,
    body: RepairOrderUpdateRequest,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Update repair order (optimistic locking via version parameter)."""
    await require_permission(db, user.id, "repair_order.update")

    try:
        ro = await RepairOrderService.update_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=user.id,
            public_id=public_id,
            submitted_version=version,
            description=body.description,
            priority=body.priority,
            estimated_cost_minor=body.estimated_cost_minor,
            estimated_cost_currency=body.estimated_cost_currency,
            notes=body.notes,
        )
        await db.commit()
        await db.refresh(ro)
        return RepairOrderDetail.model_validate(ro)
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


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repair_order(
    public_id: str,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> None:
    """Soft delete a repair order."""
    await require_permission(db, user.id, "repair_order.delete")

    try:
        await RepairOrderService.soft_delete_repair_order(
            db, garage_id=user.garage_id, user_id=user.id, public_id=public_id
        )
        await db.commit()
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{public_id}/restore", response_model=RepairOrderDetail)
async def restore_repair_order(
    public_id: str,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Restore a soft-deleted repair order."""
    await require_permission(db, user.id, "repair_order.delete")
    await require_permission(db, user.id, "admin")

    try:
        ro = await RepairOrderService.restore_repair_order(
            db, garage_id=user.garage_id, user_id=user.id, public_id=public_id
        )
        await db.commit()
        await db.refresh(ro)
        return RepairOrderDetail.model_validate(ro)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{public_id}/status-transition", response_model=RepairOrderDetail)
async def transition_status(
    public_id: str,
    body: StatusTransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Transition repair order to a new status."""
    await require_permission(db, user.id, "repair_order.transition")

    try:
        ro = await RepairOrderService.transition_status(
            db,
            garage_id=user.garage_id,
            user_id=user.id,
            public_id=public_id,
            new_status=body.new_status,
            reason=body.reason,
        )
        await db.commit()
        await db.refresh(ro)
        return RepairOrderDetail.model_validate(ro)
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


@router.post("/{public_id}/labor-lines", response_model=RepairOrderDetail)
async def add_labor_line(
    public_id: str,
    body: ROLaborLineCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Add a labor line to a repair order."""
    await require_permission(db, user.id, "repair_order.update")

    try:
        ro = await RepairOrderService.add_labor_line(
            db,
            garage_id=user.garage_id,
            user_id=user.id,
            public_id=public_id,
            labor_type=body.labor_type,
            duration_minutes=body.duration_minutes,
            rate_minor=body.rate_minor,
        )
        await db.commit()
        await db.refresh(ro)
        return RepairOrderDetail.model_validate(ro)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{public_id}/part-lines", response_model=RepairOrderDetail)
async def add_part_line(
    public_id: str,
    body: ROPartLineCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> RepairOrderDetail:
    """Add a part line to a repair order."""
    await require_permission(db, user.id, "repair_order.update")

    try:
        ro = await RepairOrderService.add_part_line(
            db,
            garage_id=user.garage_id,
            user_id=user.id,
            public_id=public_id,
            part_name=body.part_name,
            quantity=body.quantity,
            unit_cost_minor=body.unit_cost_minor,
        )
        await db.commit()
        await db.refresh(ro)
        return RepairOrderDetail.model_validate(ro)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
