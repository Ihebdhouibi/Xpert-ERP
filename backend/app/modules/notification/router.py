from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, HTTPException
from fastapi import status as http_status
from fastapi.routing import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.notification.models import NotificationTemplate
from app.modules.notification.repository import TemplateRepository
from app.modules.notification.service import render_preview
from app.modules.notification.templates_seed import SAMPLE_CONTEXTS, TRIGGER_CATALOG
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.core.logging import get_logger

router = APIRouter(tags=["notifications"])
logger = get_logger("notification.router")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    garage_id: int
    code: str
    channel: str
    locale: str
    subject: Optional[str]
    body: str
    active: bool
    updated_at: datetime
    is_override: bool = False

    @classmethod
    def from_orm_with_meta(cls, tmpl: NotificationTemplate, requesting_garage_id: int) -> "TemplateResponse":
        obj = cls.model_validate(tmpl)
        obj.is_override = tmpl.garage_id == requesting_garage_id and requesting_garage_id != 0
        return obj


class TemplateUpdateRequest(BaseModel):
    subject: Optional[str] = Field(None, max_length=500)
    body: str = Field(..., min_length=1)
    active: bool = True


class PreviewRequest(BaseModel):
    context: Optional[dict[str, Any]] = None


class PreviewResponse(BaseModel):
    subject: Optional[str]
    body: str


class TriggerEntry(BaseModel):
    code: str
    label: str
    description: str
    type: str
    channels: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/notification-templates/triggers",
    response_model=list[TriggerEntry],
    dependencies=[require_permission("notification.read")],
)
async def list_triggers(user: AuthUser) -> list[TriggerEntry]:
    """Return the full trigger catalog with metadata."""
    return [TriggerEntry(**t) for t in TRIGGER_CATALOG]


@router.get(
    "/notification-templates",
    response_model=list[TemplateResponse],
    dependencies=[require_permission("notification.read")],
)
async def list_templates(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[TemplateResponse]:
    templates = await TemplateRepository.list_for_admin(db, user.garage_id)
    return [TemplateResponse.from_orm_with_meta(t, user.garage_id) for t in templates]


@router.get(
    "/notification-templates/{template_id}",
    response_model=TemplateResponse,
    dependencies=[require_permission("notification.read")],
)
async def get_template(
    template_id: int,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    tmpl = await TemplateRepository.get_by_id(db, template_id, user.garage_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse.from_orm_with_meta(tmpl, user.garage_id)


@router.put(
    "/notification-templates/{template_id}",
    response_model=TemplateResponse,
    dependencies=[require_permission("notification.template.manage")],
)
async def update_template(
    template_id: int,
    body: TemplateUpdateRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Update or create a garage-level override for this template."""
    existing = await TemplateRepository.get_by_id(db, template_id, user.garage_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")

    # If the caller is editing a system template (garage_id=0), create a garage override
    if existing.garage_id == 0 and user.garage_id != 0:
        tmpl = await TemplateRepository.upsert(
            db,
            garage_id=user.garage_id,
            code=existing.code,
            channel=existing.channel,
            locale=existing.locale,
            subject=body.subject,
            body=body.body,
            active=body.active,
        )
    else:
        tmpl = await TemplateRepository.upsert(
            db,
            garage_id=existing.garage_id,
            code=existing.code,
            channel=existing.channel,
            locale=existing.locale,
            subject=body.subject,
            body=body.body,
            active=body.active,
        )

    await db.commit()
    await db.refresh(tmpl)
    return TemplateResponse.from_orm_with_meta(tmpl, user.garage_id)


@router.post(
    "/notification-templates/{template_id}/preview",
    response_model=PreviewResponse,
    dependencies=[require_permission("notification.read")],
)
async def preview_template(
    template_id: int,
    req: PreviewRequest,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    """Render the template with sample (or provided) context and return the output."""
    tmpl = await TemplateRepository.get_by_id(db, template_id, user.garage_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    context = req.context or SAMPLE_CONTEXTS.get(tmpl.code, {})
    subject, body = await render_preview(
        db,
        garage_id=user.garage_id,
        template_id=template_id,
        context=context,
    )
    return PreviewResponse(subject=subject, body=body)
