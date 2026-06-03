"""
Admin endpoints for managing runtime CFG_* settings stored in the DB.

All write endpoints require the config.write permission.
Read endpoints require config.read.

garage_id defaults to 0 (global).  A super-admin can pass an explicit
garage_id query parameter to manage per-garage overrides.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.config.schemas import (
    GarageSettingListResponse,
    GarageSettingOut,
    GarageSettingUpsertRequest,
)
from app.modules.config.service import SettingsService
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/settings", tags=["config"])


def _svc(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SettingsService:
    return SettingsService(db=db, redis=redis)


@router.get(
    "",
    response_model=GarageSettingListResponse,
    dependencies=[require_permission("config.read")],
)
async def list_settings(
    user: AuthUser,
    garage_id: int = Query(0, description="0 = global defaults; omit to use 0"),
    svc: SettingsService = Depends(_svc),
) -> GarageSettingListResponse:
    rows = await svc.list_settings(garage_id=garage_id)
    return GarageSettingListResponse(
        items=[GarageSettingOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get(
    "/{key}",
    response_model=GarageSettingOut,
    dependencies=[require_permission("config.read")],
)
async def get_setting(
    key: str,
    user: AuthUser,
    garage_id: int = Query(0),
    svc: SettingsService = Depends(_svc),
) -> GarageSettingOut:
    rows = await svc.list_settings(garage_id=garage_id)
    row = next((r for r in rows if r.key == key), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found for garage_id={garage_id}")
    return GarageSettingOut.model_validate(row)


@router.put(
    "/{key}",
    response_model=GarageSettingOut,
    dependencies=[require_permission("config.write")],
)
async def upsert_setting(
    key: str,
    body: GarageSettingUpsertRequest,
    user: AuthUser,
    garage_id: int = Query(0),
    svc: SettingsService = Depends(_svc),
) -> GarageSettingOut:
    row = await svc.upsert_setting(
        key=key,
        value=body.value,
        garage_id=garage_id,
        description=body.description,
        user_id=user.user_id,
    )
    return GarageSettingOut.model_validate(row)


@router.delete(
    "/{key}",
    status_code=204,
    response_class=Response,
    dependencies=[require_permission("config.write")],
)
async def delete_setting(
    key: str,
    user: AuthUser,
    garage_id: int = Query(0),
    svc: SettingsService = Depends(_svc),
) -> Response:
    deleted = await svc.delete_setting(key=key, garage_id=garage_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found for garage_id={garage_id}")
    return Response(status_code=204)
