"""Inspection module HTTP endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.modules.auth.models import AppUser
from app.modules.inspection.models import InspectionStatus
from app.modules.inspection.repository import (
    InspectionRepository,
    InspectionTemplateRepository,
    VehicleRecommendationRepository,
)
from app.modules.inspection.schemas import (
    ApprovalPublicInspection,
    ApprovalPublicItem,
    ApprovalPublicSection,
    ArchiveDeclinedRequest,
    BulkResultsRequest,
    BulkResultsResponse,
    ConflictLogEntry,
    ConvertToRORequest,
    GenerateApprovalLinkResponse,
    InspectionCreateRequest,
    InspectionDetail,
    InspectionListResponse,
    InspectionStatusTransitionRequest,
    InspectionSummary,
    InspectionTemplateCreateRequest,
    InspectionTemplateListResponse,
    InspectionTemplateSummary,
    InspectionTemplateUpdateRequest,
    ItemResultResponse,
    ProcessApprovalRequest,
    ProcessApprovalResponse,
    VehicleRecommendationResponse,
)
from app.modules.inspection.service import (
    InspectionAlreadyLinkedError,
    InspectionNotFoundError,
    InvalidInspectionStatusTransitionError,
    TemplateNotFoundError,
    TemplateVersionConflictError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenInvalidError,
    archive_declined_items,
    build_approval_public_inspection,
    convert_to_repair_order,
    create_inspection,
    create_template,
    delete_template,
    generate_approval_link,
    get_inspection_for_approval,
    process_approval,
    submit_results,
    transition_inspection,
    update_template,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(tags=["inspections"])


async def _resolve_user_id(db: AsyncSession, public_id: str) -> Optional[int]:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(AppUser.id).where(AppUser.public_id == uid))
    row = result.first()
    return row[0] if row else None


async def _resolve_ro_id(db: AsyncSession, garage_id: int, public_id: str) -> Optional[int]:
    from app.modules.repair_order.models import RepairOrder
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(
        select(RepairOrder.id).where(
            RepairOrder.public_id == uid,
            RepairOrder.garage_id == garage_id,
        )
    )
    row = result.first()
    return row[0] if row else None


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get(
    "/inspection-templates",
    response_model=InspectionTemplateListResponse,
    dependencies=[require_permission("inspection.read")],
)
async def list_templates(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_deleted: bool = False,
) -> InspectionTemplateListResponse:
    templates, total = await InspectionTemplateRepository.list(
        db,
        garage_id=user.garage_id,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    return InspectionTemplateListResponse(
        items=[InspectionTemplateSummary.from_orm(t) for t in templates],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/inspection-templates",
    response_model=InspectionTemplateSummary,
    status_code=201,
    dependencies=[require_permission("inspection.write")],
)
async def create_template_endpoint(
    body: InspectionTemplateCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionTemplateSummary:
    user_id = await _resolve_user_id(db, user.public_id)
    template = await create_template(
        db,
        garage_id=user.garage_id,
        name=body.name,
        sections=[s.model_dump() for s in body.sections],
        created_by_user_id=user_id,
    )
    await db.commit()
    return InspectionTemplateSummary.from_orm(template)


@router.get(
    "/inspection-templates/{public_id}",
    response_model=InspectionTemplateSummary,
    dependencies=[require_permission("inspection.read")],
)
async def get_template(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionTemplateSummary:
    template = await InspectionTemplateRepository.get_by_public_id(
        db, user.garage_id, public_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return InspectionTemplateSummary.from_orm(template)


@router.put(
    "/inspection-templates/{public_id}",
    response_model=InspectionTemplateSummary,
    dependencies=[require_permission("inspection.write")],
)
async def update_template_endpoint(
    public_id: str,
    body: InspectionTemplateUpdateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionTemplateSummary:
    sections = [s.model_dump() for s in body.sections] if body.sections is not None else None
    try:
        template = await update_template(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            name=body.name,
            sections=sections,
            version=body.version,
        )
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except TemplateVersionConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await db.commit()
    return InspectionTemplateSummary.from_orm(template)


@router.delete(
    "/inspection-templates/{public_id}",
    status_code=204,
    dependencies=[require_permission("inspection.write")],
)
async def delete_template_endpoint(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_template(db, garage_id=user.garage_id, public_id=public_id)
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.commit()


# ── Inspections ───────────────────────────────────────────────────────────────

@router.get(
    "/inspections",
    response_model=InspectionListResponse,
    dependencies=[require_permission("inspection.read")],
)
async def list_inspections(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    status: Optional[InspectionStatus] = None,
    mechanic_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InspectionListResponse:
    inspections, total = await InspectionRepository.list(
        db,
        garage_id=user.garage_id,
        status=status,
        mechanic_id=mechanic_id,
        vehicle_id=vehicle_id,
        page=page,
        page_size=page_size,
    )
    items = [
        InspectionSummary(
            id=str(insp.public_id),
            template_id=str(insp.template.public_id),
            template_name=insp.template.name,
            mechanic_id=insp.mechanic_id,
            repair_order_id=None,
            vehicle_id=insp.vehicle_id,
            status=insp.status.value,
            started_at=insp.started_at,
            completed_at=insp.completed_at,
            created_at=insp.created_at,
        )
        for insp in inspections
    ]
    return InspectionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/inspections",
    response_model=InspectionDetail,
    status_code=201,
    dependencies=[require_permission("inspection.write")],
)
async def create_inspection_endpoint(
    body: InspectionCreateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionDetail:
    user_id = await _resolve_user_id(db, user.public_id)
    ro_internal_id = None
    if body.repair_order_public_id:
        ro_internal_id = await _resolve_ro_id(db, user.garage_id, body.repair_order_public_id)
        if ro_internal_id is None:
            raise HTTPException(status_code=404, detail="Repair order not found")
    try:
        inspection = await create_inspection(
            db,
            garage_id=user.garage_id,
            template_public_id=body.template_public_id,
            mechanic_id=body.mechanic_id,
            repair_order_id=ro_internal_id,
            vehicle_id=body.vehicle_id,
            created_by_user_id=user_id,
        )
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.commit()
    full = await InspectionRepository.get_by_public_id(
        db, user.garage_id, str(inspection.public_id), load_results=True
    )
    return _to_detail(full)


@router.get(
    "/inspections/{public_id}",
    response_model=InspectionDetail,
    dependencies=[require_permission("inspection.read")],
)
async def get_inspection(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionDetail:
    inspection = await InspectionRepository.get_by_public_id(
        db, user.garage_id, public_id, load_results=True
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return _to_detail(inspection)


@router.put(
    "/inspections/{public_id}/status",
    response_model=InspectionSummary,
    dependencies=[require_permission("inspection.write")],
)
async def transition_status_endpoint(
    public_id: str,
    body: InspectionStatusTransitionRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionSummary:
    try:
        new_status = InspectionStatus(body.new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.new_status}")
    try:
        inspection = await transition_inspection(
            db, garage_id=user.garage_id, public_id=public_id, new_status=new_status
        )
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except InvalidInspectionStatusTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await db.commit()
    return InspectionSummary(
        id=str(inspection.public_id),
        template_id=str(inspection.template_id),
        template_name="",
        mechanic_id=inspection.mechanic_id,
        repair_order_id=None,
        vehicle_id=inspection.vehicle_id,
        status=inspection.status.value,
        started_at=inspection.started_at,
        completed_at=inspection.completed_at,
        created_at=inspection.created_at,
    )


@router.post(
    "/inspections/{public_id}/results",
    response_model=BulkResultsResponse,
    dependencies=[require_permission("inspection.write")],
)
async def submit_bulk_results(
    public_id: str,
    body: BulkResultsRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> BulkResultsResponse:
    items = [
        {
            "item_id": it.item_id,
            "status": it.status,
            "notes": it.notes,
            "media_ids": it.media_ids,
            "written_at": it.written_at,
        }
        for it in body.items
    ]
    try:
        _, conflicts = await submit_results(
            db, garage_id=user.garage_id, public_id=public_id, items=items
        )
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")
    await db.commit()
    return BulkResultsResponse(
        synced=len(items) - len(conflicts),
        conflicts=[
            ConflictLogEntry(
                item_id=c.item_id,
                client_written_at=c.client_written_at,
                server_written_at=c.server_written_at,
                discarded_status=c.discarded_status,
                kept_status=c.kept_status,
            )
            for c in conflicts
        ],
    )


@router.post(
    "/inspections/{public_id}/recommendations",
    response_model=list[VehicleRecommendationResponse],
    status_code=201,
    dependencies=[require_permission("inspection.write")],
)
async def archive_declined_endpoint(
    public_id: str,
    body: ArchiveDeclinedRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[VehicleRecommendationResponse]:
    user_id = await _resolve_user_id(db, user.public_id)
    try:
        recs = await archive_declined_items(
            db,
            garage_id=user.garage_id,
            inspection_public_id=public_id,
            vehicle_id=body.vehicle_id,
            declined_items=[d.model_dump() for d in body.declined_items],
            created_by_user_id=user_id,
        )
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await db.commit()
    return [VehicleRecommendationResponse.from_orm(r) for r in recs]


@router.post(
    "/inspections/{public_id}/convert-to-ro",
    response_model=InspectionSummary,
    dependencies=[require_permission("inspection.write")],
)
async def convert_to_ro_endpoint(
    public_id: str,
    body: ConvertToRORequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> InspectionSummary:
    ro_id = await _resolve_ro_id(db, user.garage_id, body.repair_order_public_id)
    if ro_id is None:
        raise HTTPException(status_code=404, detail="Repair order not found")
    try:
        inspection = await convert_to_repair_order(
            db, garage_id=user.garage_id, public_id=public_id, repair_order_id=ro_id
        )
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except InspectionAlreadyLinkedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await db.commit()
    return InspectionSummary(
        id=str(inspection.public_id),
        template_id=str(inspection.template_id),
        template_name="",
        mechanic_id=inspection.mechanic_id,
        repair_order_id=body.repair_order_public_id,
        vehicle_id=inspection.vehicle_id,
        status=inspection.status.value,
        started_at=inspection.started_at,
        completed_at=inspection.completed_at,
        created_at=inspection.created_at,
    )


# ── PDF report ────────────────────────────────────────────────────────────────

@router.get(
    "/inspections/{public_id}/report.pdf",
    dependencies=[require_permission("inspection.read")],
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {},
        422: {},
    },
)
async def download_inspection_report(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    inspection = await InspectionRepository.get_by_public_id(
        db, user.garage_id, public_id
    )
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if inspection.status != InspectionStatus.completed:
        raise HTTPException(
            status_code=422, detail="Inspection must be completed to generate a report"
        )
    from app.modules.inspection.pdf_service import generate_pdf
    pdf_bytes = await generate_pdf(db, inspection, settings)
    filename = f"inspection-{public_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Approval link ──────────────────────────────────────────────────────────────

@router.post(
    "/inspections/{public_id}/approval-link",
    response_model=GenerateApprovalLinkResponse,
    status_code=201,
    dependencies=[require_permission("inspection.write")],
)
async def create_approval_link(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GenerateApprovalLinkResponse:
    try:
        token_str, token_record = await generate_approval_link(
            db,
            garage_id=user.garage_id,
            inspection_public_id=public_id,
            expiry_days=settings.cfg_inspection_approval_expiry_days,
            secret_key=settings.secret_key,
            algorithm=settings.algorithm,
        )
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    return GenerateApprovalLinkResponse(token=token_str, expires_at=token_record.expires_at)


# ── Public approval endpoints (no auth) ───────────────────────────────────────

@router.get(
    "/inspections/approve/{token}",
    response_model=ApprovalPublicInspection,
)
async def get_approval_page(
    token: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApprovalPublicInspection:
    try:
        inspection, _ = await get_inspection_for_approval(
            db,
            token_str=token,
            secret_key=settings.secret_key,
            algorithm=settings.algorithm,
        )
    except (TokenExpiredError, TokenInvalidError):
        raise HTTPException(status_code=404, detail="Invalid or expired approval link")
    except TokenAlreadyUsedError:
        raise HTTPException(status_code=410, detail="Approval link has already been used")
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")

    data = await build_approval_public_inspection(db, inspection)
    return ApprovalPublicInspection(
        inspection_id=data["inspection_id"],
        template_name=data["template_name"],
        vehicle_info=data["vehicle_info"],
        mechanic_name=data["mechanic_name"],
        completed_at=data["completed_at"],
        sections=[
            ApprovalPublicSection(
                section_id=s["section_id"],
                section_title=s["section_title"],
                items=[ApprovalPublicItem(**i) for i in s["items"]],
            )
            for s in data["sections"]
        ],
    )


@router.post(
    "/inspections/approve/{token}",
    response_model=ProcessApprovalResponse,
)
async def submit_approval(
    token: str,
    body: ProcessApprovalRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProcessApprovalResponse:
    try:
        result = await process_approval(
            db,
            token_str=token,
            decisions=[d.model_dump() for d in body.decisions],
            secret_key=settings.secret_key,
            algorithm=settings.algorithm,
        )
    except (TokenExpiredError, TokenInvalidError):
        raise HTTPException(status_code=404, detail="Invalid or expired approval link")
    except TokenAlreadyUsedError:
        raise HTTPException(status_code=410, detail="Approval link has already been used")
    except InspectionNotFoundError:
        raise HTTPException(status_code=404, detail="Inspection not found")
    await db.commit()
    return ProcessApprovalResponse(**result)


# ── Vehicle recommendations ───────────────────────────────────────────────────

@router.get(
    "/vehicles/{vehicle_id}/recommendations",
    response_model=list[VehicleRecommendationResponse],
    dependencies=[require_permission("inspection.read")],
)
async def list_vehicle_recommendations(
    vehicle_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[VehicleRecommendationResponse]:
    recs = await VehicleRecommendationRepository.list_for_vehicle(
        db, user.garage_id, vehicle_id
    )
    return [VehicleRecommendationResponse.from_orm(r) for r in recs]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_detail(inspection) -> InspectionDetail:  # type: ignore[no-untyped-def]
    return InspectionDetail(
        id=str(inspection.public_id),
        template_id=str(inspection.template.public_id),
        template_name=inspection.template.name,
        template_sections=inspection.template.sections,
        mechanic_id=inspection.mechanic_id,
        repair_order_id=None,
        vehicle_id=inspection.vehicle_id,
        status=inspection.status.value,
        started_at=inspection.started_at,
        completed_at=inspection.completed_at,
        created_at=inspection.created_at,
        results=[ItemResultResponse.from_orm(r) for r in inspection.results],
        version=inspection.version,
    )
