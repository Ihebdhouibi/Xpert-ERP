"""Repair Order module HTTP endpoints."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.models import AppUser
from app.modules.repair_order.models import ROStatus
from app.modules.repair_order.repository import RepairOrderRepository
from app.modules.repair_order.schemas import (
    AssignMechanicRequest,
    RepairOrderCreateRequest,
    RepairOrderDetail,
    RepairOrderSummary,
    RepairOrderUpdateRequest,
    ROLaborLineCreateRequest,
    ROPartLineCreateRequest,
    ROPhotoListResponse,
    ROPhotoSummary,
    StatusTransitionRequest,
)
from app.modules.repair_order.service import (
    InvalidStatusTransitionError,
    OptimisticLockError,
    RepairOrderNotFoundError,
    RepairOrderService,
)
from app.modules.rbac.dependencies import AuthUser, require_permission, require_role
from app.core.logging import get_logger

router = APIRouter(prefix="/repair-orders", tags=["repair-orders"])
logger = get_logger("repair_order.router")


async def _customer_name(db: AsyncSession, garage_id: int, customer_id: Optional[int]) -> Optional[str]:
    """Resolve a customer's display name (full name, optionally with company)."""
    if customer_id is None:
        return None
    from app.modules.customer import repository as customer_repo

    customer = await customer_repo.get_by_id(db, garage_id, customer_id)
    if not customer:
        return None
    return (
        f"{customer.full_name} ({customer.company_name})"
        if customer.company_name
        else customer.full_name
    )


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
    detail = RepairOrderDetail.model_validate(ro)
    detail.customer_name = await _customer_name(db, garage_id, ro.customer_id)
    return detail


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
    assigned_user_id: Optional[int] = None,
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
        assigned_user_id=assigned_user_id,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    items = []
    for ro in rows:
        summary = RepairOrderSummary.model_validate(ro)
        summary.customer_name = await _customer_name(db, user.garage_id, ro.customer_id)
        items.append(summary)
    return {
        "items": items,
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
        ro = await RepairOrderService.soft_delete_repair_order(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
        )
        # Release all stock reservations held by this RO — same transaction
        from app.modules.parts.stock_service import release_all_for_ref
        await release_all_for_ref(
            db,
            garage_id=user.garage_id,
            ref_type="repair_order",
            ref_id=str(ro.public_id),
            created_by_user_id=actor_id or user.user_id,
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
    """Transition repair order to a new status.

    When transitioning to in_repair, all pending reservations are converted
    to committed stock-out movements atomically.
    """
    from app.core.config import get_settings
    from app.modules.parts.stock_service import NegativeStockError
    settings = get_settings()
    actor_id = await _resolve_user_id(db, user.public_id)
    try:
        await RepairOrderService.transition_status(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
            new_status=body.new_status,
            reason=body.reason,
            allow_negative_stock=settings.cfg_allow_negative_stock,
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
    except NegativeStockError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "negative_stock_on_commit",
                "available": e.available,
                "requested": e.requested,
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
    from app.modules.parts.stock_service import NegativeStockError
    try:
        await RepairOrderService.add_part_line(
            db,
            garage_id=user.garage_id,
            user_id=actor_id or user.user_id,
            public_id=public_id,
            part_name=body.part_name,
            quantity=body.quantity,
            unit_cost_minor=body.unit_cost_minor,
            part_public_id=body.part_public_id,
        )
        await db.commit()
        return await _get_detail(db, user.garage_id, public_id)
    except RepairOrderNotFoundError:
        raise HTTPException(status_code=404, detail="Repair order not found")
    except NegativeStockError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "negative_stock",
                "available": e.available,
                "requested": e.requested,
            },
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{public_id}/assign",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.update")],
)
async def assign_mechanic(
    public_id: str,
    body: AssignMechanicRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Assign (or unassign) a mechanic to a repair order."""
    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")
    ro.assigned_user_id = body.user_id
    await db.commit()
    return await _get_detail(db, user.garage_id, public_id)


@router.post(
    "/{public_id}/photos",
    response_model=ROPhotoSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("repair_order.update")],
)
async def upload_photo(
    public_id: str,
    user: AuthUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ROPhotoSummary:
    """Upload a photo for a repair order (stored in S3)."""
    import uuid as _uuid
    from app.modules.documents.storage import upload_bytes
    from app.core.config import get_settings

    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    allowed = {"image/jpeg", "image/png", "image/webp", "image/heic"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {file.content_type}",
        )

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    settings = get_settings()
    storage_key = f"repair-orders/{ro.id}/photos/{_uuid.uuid4()}/{file.filename}"
    await upload_bytes(bucket=settings.s3_bucket_media, key=storage_key, data=data, content_type=file.content_type)

    actor_id = await _resolve_user_id(db, user.public_id)
    photo = await RepairOrderRepository.add_photo(
        db,
        ro_id=ro.id,
        garage_id=user.garage_id,
        storage_key=storage_key,
        filename=file.filename or "upload",
        mime_type=file.content_type,
        size_bytes=len(data),
        uploaded_by_user_id=actor_id,
    )
    await db.commit()
    await db.refresh(photo)

    from app.modules.documents.storage import generate_presigned_url
    url = await generate_presigned_url(bucket=settings.s3_bucket_media, key=storage_key, expiry_seconds=3600)
    result = ROPhotoSummary.model_validate(photo)
    result.url = url
    return result


@router.get(
    "/{public_id}/pdf",
    dependencies=[require_permission("repair_order.read")],
)
async def get_pdf_report(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate and return a presigned URL to the repair order PDF report."""
    from app.core.config import get_settings
    from app.modules.repair_order.pdf_service import generate_pdf, upload_pdf_and_sign

    ro = await RepairOrderRepository.get_by_public_id(
        db, user.garage_id, public_id, load_relationships=True
    )
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    settings = get_settings()
    try:
        pdf_bytes = await generate_pdf(db, ro, settings)
        url = await upload_pdf_and_sign(pdf_bytes, ro, settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    return {"url": url, "expires_in": settings.signed_url_expiry_seconds}


@router.get(
    "/{public_id}/photos",
    response_model=ROPhotoListResponse,
    dependencies=[require_permission("repair_order.read")],
)
async def list_photos(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> ROPhotoListResponse:
    """List all photos for a repair order with presigned download URLs."""
    from app.modules.documents.storage import generate_presigned_url
    from app.core.config import get_settings

    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    settings = get_settings()
    photos = await RepairOrderRepository.list_photos(db, ro.id)

    items: list[ROPhotoSummary] = []
    for p in photos:
        url = await generate_presigned_url(
            bucket=settings.s3_bucket_media,
            key=p.storage_key,
            expiry_seconds=3600,
        )
        summary = ROPhotoSummary.model_validate(p)
        summary.url = url
        items.append(summary)

    return ROPhotoListResponse(items=items, total=len(items))
