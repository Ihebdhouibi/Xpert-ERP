"""Repair Order module HTTP endpoints."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.models import AppUser
from app.modules.repair_order.models import ROStatus
from app.modules.repair_order.repository import RepairOrderRepository
from app.modules.repair_order.schemas import (
    AssignMechanicRequest,
    DiagnosisRequest,
    MechanicSummary,
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
    StepIncompleteError,
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


async def _user_name(db: AsyncSession, user_id: Optional[int]) -> Optional[str]:
    """Resolve an app_user id to a display name."""
    if user_id is None:
        return None
    row = await db.execute(select(AppUser.full_name).where(AppUser.id == user_id))
    return row.scalar_one_or_none()


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
    detail.assigned_user_name = await _user_name(db, ro.assigned_user_id)
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
    """List repair orders with optional filters and pagination.

    Mechanics only see the repair orders assigned to them; reception/admin see all.
    """
    _PRIVILEGED = {"admin", "super_admin", "secretary"}
    if "mechanic" in user.roles and not (_PRIVILEGED & set(user.roles)):
        assigned_user_id = user.user_id

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


# NOTE: must be declared before "/{public_id}" so it isn't captured by it.
@router.get(
    "/mechanics",
    response_model=list[MechanicSummary],
    dependencies=[require_permission("repair_order.read")],
)
async def list_mechanics(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[MechanicSummary]:
    """List active mechanics with their current open workload (for assignment)."""
    from app.modules.auth.models import Role, UserRole, UserStatus
    from app.modules.repair_order.models import RepairOrder, ROStatus

    rows = await db.execute(
        select(AppUser.id, AppUser.full_name)
        .join(UserRole, UserRole.user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            AppUser.garage_id == user.garage_id,
            AppUser.deleted_at.is_(None),
            AppUser.status == UserStatus.active,
            Role.code == "mechanic",
        )
        .order_by(AppUser.full_name)
    )
    mechanics = list(dict.fromkeys(rows.all()))  # de-dupe if multiple roles

    open_statuses = [
        ROStatus.created, ROStatus.diagnosis, ROStatus.in_repair,
        ROStatus.paused_parts,
    ]
    result: list[MechanicSummary] = []
    for uid, name in mechanics:
        count = (
            await db.execute(
                select(func.count())
                .select_from(RepairOrder)
                .where(
                    RepairOrder.garage_id == user.garage_id,
                    RepairOrder.assigned_user_id == uid,
                    RepairOrder.deleted_at.is_(None),
                    RepairOrder.status.in_(open_statuses),
                )
            )
        ).scalar_one()
        result.append(MechanicSummary(id=uid, name=name, active_orders=int(count)))
    return result


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
    except StepIncompleteError as e:
        raise HTTPException(status_code=422, detail=e.message)
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
    dependencies=[require_permission("repair_order.transition")],
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
    dependencies=[require_permission("repair_order.transition")],
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
            remise_pct=body.remise_pct,
            tva_pct=body.tva_pct,
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
    background_tasks: BackgroundTasks,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Assign (or unassign) a mechanic and notify them (acceptance reset)."""
    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")
    ro.assigned_user_id = body.user_id
    # A new assignment must be (re)accepted by the mechanic or a secretary.
    ro.assignment_accepted_at = None
    await db.commit()

    # Notify the newly assigned mechanic: in-app (always) + email (best-effort).
    if body.user_id is not None:
        from app.modules.notification.inbox_router import create_app_notification

        description = ro.description or "Aucune description fournie"
        await create_app_notification(
            db,
            garage_id=user.garage_id,
            recipient_id=body.user_id,
            title="Nouvel ordre de réparation assigné",
            body=description,
            link=f"/repair-orders/{ro.public_id}",
        )
        await db.commit()

        mech = (await db.execute(select(AppUser).where(AppUser.id == body.user_id))).scalar_one_or_none()
        if mech and mech.email:
            background_tasks.add_task(
                _notify_assignment, user.garage_id, mech.id, mech.email, ro.public_id, description
            )
    return await _get_detail(db, user.garage_id, public_id)


async def _notify_assignment(
    garage_id: int, mechanic_id: int, email: str, ro_public_id, description: str
) -> None:
    """Send an 'assigned to a repair order' notification (best-effort)."""
    from app.core.database import AsyncSessionFactory
    from app.modules.notification import service as notif_service

    try:
        async with AsyncSessionFactory() as db:
            await notif_service.dispatch(
                db,
                garage_id=garage_id,
                recipient_id=mechanic_id,
                recipient=email,
                channel="email",
                template_code="repair_order_assigned",
                context={
                    "subject": "Nouvel ordre de réparation assigné",
                    "ro_id": str(ro_public_id),
                    "description": description,
                },
            )
    except Exception as exc:  # notification must never break assignment
        logger.warning("ro_assignment_notify_failed", error=str(exc))


@router.post(
    "/{public_id}/accept-assignment",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.transition")],
)
async def accept_assignment(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Accept the assignment — by the assigned mechanic, or a secretary on their behalf."""
    from datetime import datetime, timezone

    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")
    if ro.assigned_user_id is None:
        raise HTTPException(status_code=409, detail="No mechanic assigned to accept")
    ro.assignment_accepted_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return await _get_detail(db, user.garage_id, public_id)


@router.put(
    "/{public_id}/diagnosis",
    response_model=RepairOrderDetail,
    dependencies=[require_permission("repair_order.transition")],
)
async def save_diagnosis(
    public_id: str,
    body: DiagnosisRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> RepairOrderDetail:
    """Save diagnosis answers (D1..D5 + notes). Marking completed stamps the date."""
    from datetime import datetime, timezone

    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    if body.completed:
        from app.modules.repair_order.schemas import DIAGNOSIS_QUESTIONS

        missing = [code for code, _ in DIAGNOSIS_QUESTIONS if code not in body.answers]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Diagnostic incomplet : répondez à toutes les questions ({', '.join(missing)}).",
            )

    ro.diagnosis = {"answers": body.answers, "notes": body.notes}
    if body.completed:
        ro.diagnosis_completed_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return await _get_detail(db, user.garage_id, public_id)


@router.post(
    "/{public_id}/photos",
    response_model=ROPhotoSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("repair_order.media.upload")],
)
async def upload_photo(
    public_id: str,
    user: AuthUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ROPhotoSummary:
    """Upload a photo or video for a repair order (stored in S3/MinIO media bucket)."""
    import uuid as _uuid
    from app.modules.documents.storage import upload_bytes
    from app.core.config import get_settings

    ro = await RepairOrderRepository.get_by_public_id(db, user.garage_id, public_id)
    if not ro:
        raise HTTPException(status_code=404, detail="Repair order not found")

    allowed = {
        "image/jpeg", "image/png", "image/webp", "image/heic",
        "video/mp4", "video/quicktime", "video/webm",
    }
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {file.content_type}",
        )

    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

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
