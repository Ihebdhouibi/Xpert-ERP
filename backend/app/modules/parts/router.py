"""Parts catalog HTTP endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.parts.models import PartStatus
from app.modules.parts.repository import PartCategoryRepository, PartRepository
from app.modules.parts.schemas import (
    EquivalentLinkRequest,
    PartCategoryCreate,
    PartCategorySummary,
    PartCategoryUpdate,
    PartCreate,
    PartDetail,
    PartListResponse,
    PartSummary,
    PartUpdate,
)
from app.modules.parts.service import (
    CategoryHasPartsError,
    CategoryNotFoundError,
    EquivalentAlreadyLinkedError,
    EquivalentNotFoundError,
    EquivalentSelfLinkError,
    PartNotFoundError,
    PartSKUConflictError,
    PartVersionConflictError,
    create_category,
    create_part,
    delete_category,
    link_equivalents,
    soft_delete_part,
    unlink_equivalents,
    update_category,
    update_part,
)
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.core.logging import get_logger

router = APIRouter(tags=["parts"])
logger = get_logger("parts.router")


# ===========================================================================
# Part Categories
# ===========================================================================

@router.get(
    "/part-categories",
    response_model=list[PartCategorySummary],
    dependencies=[require_permission("part.read")],
)
async def list_categories(
    user: AuthUser,
    parent_id: Optional[int] = None,
    flat: bool = Query(False, description="Return all categories (ignore parent_id filter)"),
    db: AsyncSession = Depends(get_db),
) -> list[PartCategorySummary]:
    cats = await PartCategoryRepository.list(db, user.garage_id, parent_id=parent_id, flat=flat)
    return [PartCategorySummary.model_validate(c) for c in cats]


@router.post(
    "/part-categories",
    response_model=PartCategorySummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("part.create")],
)
async def create_category_endpoint(
    body: PartCategoryCreate,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PartCategorySummary:
    try:
        cat = await create_category(
            db, user.garage_id, body.name, body.description, body.parent_id
        )
        await db.commit()
        await db.refresh(cat)
        return PartCategorySummary.model_validate(cat)
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/part-categories/{category_id}",
    response_model=PartCategorySummary,
    dependencies=[require_permission("part.update")],
)
async def update_category_endpoint(
    category_id: int,
    body: PartCategoryUpdate,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PartCategorySummary:
    try:
        cat = await update_category(
            db, user.garage_id, category_id, body.name, body.description, body.parent_id
        )
        await db.commit()
        await db.refresh(cat)
        return PartCategorySummary.model_validate(cat)
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/part-categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("part.delete")],
)
async def delete_category_endpoint(
    category_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_category(db, user.garage_id, category_id)
        await db.commit()
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CategoryHasPartsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Parts
# ===========================================================================

async def _get_part_detail(
    db: AsyncSession, garage_id: int, public_id: str
) -> PartDetail:
    part = await PartRepository.get_by_public_id(
        db, garage_id, public_id, load_category=True
    )
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    equivalents = await PartRepository.get_equivalents(db, part.id)
    detail = PartDetail.model_validate(part)
    detail.equivalents = [PartSummary.model_validate(p) for p in equivalents]
    return detail


@router.get(
    "/parts",
    response_model=PartListResponse,
    dependencies=[require_permission("part.read")],
)
async def list_parts(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[PartStatus] = None,
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PartListResponse:
    parts, total = await PartRepository.list(
        db,
        garage_id=user.garage_id,
        search=search,
        category_id=category_id,
        status=status,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    return PartListResponse(
        items=[PartSummary.model_validate(p) for p in parts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/parts/{public_id}",
    response_model=PartDetail,
    dependencies=[require_permission("part.read")],
)
async def get_part(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PartDetail:
    return await _get_part_detail(db, user.garage_id, public_id)


@router.post(
    "/parts",
    response_model=PartDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("part.create")],
)
async def create_part_endpoint(
    body: PartCreate,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PartDetail:
    try:
        await create_part(
            db,
            garage_id=user.garage_id,
            sku_code=body.sku_code,
            name=body.name,
            description=body.description,
            category_id=body.category_id,
            unit_of_measure=body.unit_of_measure,
            purchase_price_minor=body.purchase_price_minor,
            selling_price_minor=body.selling_price_minor,
            supplier_hint_id=body.supplier_hint_id,
            reorder_threshold=body.reorder_threshold,
            reorder_quantity=body.reorder_quantity,
            status=body.status,
        )
        await db.commit()
        part = await PartRepository.get_by_sku(db, user.garage_id, body.sku_code)
        return await _get_part_detail(db, user.garage_id, str(part.public_id))
    except PartSKUConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "sku_conflict", "sku_code": e.sku_code},
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/parts/{public_id}",
    response_model=PartDetail,
    dependencies=[require_permission("part.update")],
)
async def update_part_endpoint(
    public_id: str,
    body: PartUpdate,
    user: AuthUser,
    version: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> PartDetail:
    try:
        await update_part(
            db,
            garage_id=user.garage_id,
            public_id=public_id,
            submitted_version=version,
            **{k: v for k, v in body.model_dump().items() if v is not None},
        )
        await db.commit()
        return await _get_part_detail(db, user.garage_id, public_id)
    except PartNotFoundError:
        raise HTTPException(status_code=404, detail="Part not found")
    except PartVersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "current_version": e.current_version,
                "submitted_version": e.submitted_version,
            },
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/parts/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("part.delete")],
)
async def delete_part_endpoint(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await soft_delete_part(db, user.garage_id, public_id)
        await db.commit()
    except PartNotFoundError:
        raise HTTPException(status_code=404, detail="Part not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Equivalents
# ===========================================================================

@router.get(
    "/parts/{public_id}/equivalents",
    response_model=list[PartSummary],
    dependencies=[require_permission("part.read")],
)
async def list_equivalents(
    public_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[PartSummary]:
    part = await PartRepository.get_by_public_id(db, user.garage_id, public_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    peers = await PartRepository.get_equivalents(db, part.id)
    return [PartSummary.model_validate(p) for p in peers]


@router.post(
    "/parts/{public_id}/equivalents",
    status_code=status.HTTP_201_CREATED,
    response_model=list[PartSummary],
    dependencies=[require_permission("part.update")],
)
async def add_equivalent(
    public_id: str,
    body: EquivalentLinkRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[PartSummary]:
    try:
        await link_equivalents(db, user.garage_id, public_id, body.target_id)
        await db.commit()
        part = await PartRepository.get_by_public_id(db, user.garage_id, public_id)
        peers = await PartRepository.get_equivalents(db, part.id)
        return [PartSummary.model_validate(p) for p in peers]
    except PartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EquivalentSelfLinkError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except EquivalentAlreadyLinkedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/parts/{public_id}/equivalents/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("part.update")],
)
async def remove_equivalent(
    public_id: str,
    target_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await unlink_equivalents(db, user.garage_id, public_id, target_id)
        await db.commit()
    except PartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EquivalentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
