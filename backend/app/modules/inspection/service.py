from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inspection.models import (
    Inspection,
    InspectionApprovalToken,
    InspectionConflictLog,
    InspectionStatus,
    InspectionTemplate,
    VehicleRecommendation,
    can_transition_inspection,
)
from app.modules.inspection.repository import (
    ApprovalTokenRepository,
    InspectionRepository,
    InspectionTemplateRepository,
    VehicleRecommendationRepository,
)


class TemplateNotFoundError(Exception):
    def __init__(self, public_id: str) -> None:
        self.public_id = public_id
        super().__init__(f"Inspection template not found: {public_id}")


class TemplateVersionConflictError(Exception):
    def __init__(self, current: int, submitted: int) -> None:
        super().__init__(f"Version conflict: current={current}, submitted={submitted}")


class InspectionNotFoundError(Exception):
    def __init__(self, public_id: str) -> None:
        self.public_id = public_id
        super().__init__(f"Inspection not found: {public_id}")


class InvalidInspectionStatusTransitionError(Exception):
    def __init__(self, from_s: str, to_s: str) -> None:
        super().__init__(f"Cannot transition inspection from {from_s} to {to_s}")


class InspectionAlreadyLinkedError(Exception):
    pass


class TokenInvalidError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class TokenAlreadyUsedError(Exception):
    pass


async def create_template(
    db: AsyncSession,
    *,
    garage_id: int,
    name: str,
    sections: list,
    created_by_user_id: Optional[int] = None,
) -> InspectionTemplate:
    return await InspectionTemplateRepository.create(
        db,
        garage_id=garage_id,
        name=name,
        sections=sections,
        created_by_user_id=created_by_user_id,
    )


async def update_template(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
    name: Optional[str] = None,
    sections: Optional[list] = None,
    version: int,
) -> InspectionTemplate:
    template = await InspectionTemplateRepository.get_by_public_id(db, garage_id, public_id)
    if not template:
        raise TemplateNotFoundError(public_id)
    if template.version != version:
        raise TemplateVersionConflictError(template.version, version)
    return await InspectionTemplateRepository.update(db, template, name=name, sections=sections)


async def delete_template(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
) -> None:
    template = await InspectionTemplateRepository.get_by_public_id(db, garage_id, public_id)
    if not template:
        raise TemplateNotFoundError(public_id)
    await InspectionTemplateRepository.soft_delete(db, template)


async def create_inspection(
    db: AsyncSession,
    *,
    garage_id: int,
    template_public_id: str,
    mechanic_id: Optional[int] = None,
    repair_order_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    created_by_user_id: Optional[int] = None,
) -> Inspection:
    template = await InspectionTemplateRepository.get_by_public_id(
        db, garage_id, template_public_id
    )
    if not template:
        raise TemplateNotFoundError(template_public_id)
    return await InspectionRepository.create(
        db,
        garage_id=garage_id,
        template_id=template.id,
        mechanic_id=mechanic_id,
        repair_order_id=repair_order_id,
        vehicle_id=vehicle_id,
        created_by_user_id=created_by_user_id,
    )


async def transition_inspection(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
    new_status: InspectionStatus,
) -> Inspection:
    inspection = await InspectionRepository.get_by_public_id(db, garage_id, public_id)
    if not inspection:
        raise InspectionNotFoundError(public_id)
    if not can_transition_inspection(inspection.status, new_status):
        raise InvalidInspectionStatusTransitionError(
            inspection.status.value, new_status.value
        )
    await InspectionRepository.transition_status(db, inspection, new_status)
    return inspection


async def submit_results(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
    items: list[dict],
) -> tuple[Inspection, list[InspectionConflictLog]]:
    inspection = await InspectionRepository.get_by_public_id(
        db, garage_id, public_id, load_results=True
    )
    if not inspection:
        raise InspectionNotFoundError(public_id)
    conflicts = await InspectionRepository.bulk_upsert_results(db, inspection, items)
    return inspection, conflicts


async def archive_declined_items(
    db: AsyncSession,
    *,
    garage_id: int,
    inspection_public_id: str,
    vehicle_id: int,
    declined_items: list[dict],
    created_by_user_id: Optional[int] = None,
) -> list[VehicleRecommendation]:
    inspection = await InspectionRepository.get_by_public_id(
        db, garage_id, inspection_public_id
    )
    if not inspection:
        raise InspectionNotFoundError(inspection_public_id)
    if inspection.status != InspectionStatus.completed:
        raise ValueError("Inspection must be completed before archiving declined items")
    return await VehicleRecommendationRepository.create_bulk(
        db,
        garage_id=garage_id,
        vehicle_id=vehicle_id,
        source_inspection_id=inspection.id,
        recommendations=declined_items,
        created_by_user_id=created_by_user_id,
    )


async def convert_to_repair_order(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
    repair_order_id: int,
) -> Inspection:
    inspection = await InspectionRepository.get_by_public_id(db, garage_id, public_id)
    if not inspection:
        raise InspectionNotFoundError(public_id)
    if inspection.repair_order_id is not None:
        raise InspectionAlreadyLinkedError(
            f"Inspection {public_id} is already linked to repair order {inspection.repair_order_id}"
        )
    await InspectionRepository.set_repair_order(db, inspection, repair_order_id)
    return inspection


async def generate_approval_link(
    db: AsyncSession,
    *,
    garage_id: int,
    inspection_public_id: str,
    expiry_days: int,
    secret_key: str,
    algorithm: str,
) -> tuple[str, InspectionApprovalToken]:
    from jose import jwt as jose_jwt

    inspection = await InspectionRepository.get_by_public_id(db, garage_id, inspection_public_id)
    if not inspection:
        raise InspectionNotFoundError(inspection_public_id)
    if inspection.status != InspectionStatus.completed:
        raise ValueError("Inspection must be completed before generating an approval link")
    if inspection.repair_order_id is None:
        raise ValueError("Inspection must be linked to a repair order before generating an approval link")

    jti = str(uuid_lib.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
    payload = {
        "sub": str(inspection.public_id),
        "jti": jti,
        "exp": expires_at,
        "typ": "inspection_approval",
    }
    token_str: str = jose_jwt.encode(payload, secret_key, algorithm=algorithm)
    token_record = await ApprovalTokenRepository.create(
        db,
        jti=jti,
        inspection_id=inspection.id,
        expires_at=expires_at,
    )
    return token_str, token_record


async def get_inspection_for_approval(
    db: AsyncSession,
    *,
    token_str: str,
    secret_key: str,
    algorithm: str,
) -> tuple[Inspection, InspectionApprovalToken]:
    from jose import ExpiredSignatureError, JWTError
    from jose import jwt as jose_jwt

    try:
        payload: dict = jose_jwt.decode(token_str, secret_key, algorithms=[algorithm])
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise TokenInvalidError()

    if payload.get("typ") != "inspection_approval":
        raise TokenInvalidError()

    jti = payload.get("jti")
    if not jti:
        raise TokenInvalidError()

    token_record = await ApprovalTokenRepository.get_by_jti(db, jti)
    if not token_record:
        raise TokenInvalidError()
    if token_record.used_at is not None:
        raise TokenAlreadyUsedError()

    inspection_public_id = payload.get("sub", "")
    inspection = await InspectionRepository.get_by_public_id_any_garage(
        db, inspection_public_id, load_results=True
    )
    if not inspection:
        raise InspectionNotFoundError(inspection_public_id)

    return inspection, token_record


async def process_approval(
    db: AsyncSession,
    *,
    token_str: str,
    decisions: list[dict],
    secret_key: str,
    algorithm: str,
) -> dict:
    inspection, token_record = await get_inspection_for_approval(
        db, token_str=token_str, secret_key=secret_key, algorithm=algorithm
    )

    # Mark used first — single-use enforcement before any side effects
    await ApprovalTokenRepository.mark_used(db, token_record)

    results_map = {r.item_id: r for r in inspection.results}

    # Build item label lookup from template sections
    label_map: dict[str, str] = {}
    for section in (inspection.template.sections or []):
        for item in section.get("items", []):
            label_map[item["id"]] = item["label"]

    repair_tasks_created = 0
    recommendations_archived = 0

    for decision in decisions:
        item_id = decision["item_id"]
        action = decision["decision"]
        result = results_map.get(item_id)
        if not result:
            continue
        if result.status.value not in ("attention", "defective"):
            continue

        item_label = label_map.get(item_id, item_id)

        if action == "approved":
            from app.modules.repair_order.models import ROLaborLine
            labor_line = ROLaborLine(
                ro_id=inspection.repair_order_id,
                labor_type=item_label[:100],
                duration_minutes=0,
                rate_minor=0,
                amount_minor=0,
            )
            db.add(labor_line)
            repair_tasks_created += 1

        elif action == "rejected" and inspection.vehicle_id:
            rec = VehicleRecommendation(
                public_id=uuid_lib.uuid4(),
                garage_id=inspection.garage_id,
                vehicle_id=inspection.vehicle_id,
                source_inspection_id=inspection.id,
                item_id=item_id,
                item_label=item_label,
                item_status=result.status.value,
                status="archived",
                notes=None,
            )
            db.add(rec)
            recommendations_archived += 1

    await db.flush()
    return {
        "repair_tasks_created": repair_tasks_created,
        "recommendations_archived": recommendations_archived,
    }


async def build_approval_public_inspection(
    db: AsyncSession,
    inspection: Inspection,
) -> dict:
    """Build the public-facing inspection payload for the customer approval page."""
    results_map = {r.item_id: r for r in inspection.results}

    vehicle_info = "—"
    if inspection.vehicle_id:
        from sqlalchemy import select
        from app.modules.vehicles.models import Vehicle
        vrow = await db.execute(select(Vehicle).where(Vehicle.id == inspection.vehicle_id))
        vehicle = vrow.scalar_one_or_none()
        if vehicle:
            parts = [vehicle.make, vehicle.model]
            if vehicle.year:
                parts.append(str(vehicle.year))
            if vehicle.registration:
                parts.append(f"({vehicle.registration})")
            vehicle_info = " ".join(parts)

    mechanic_name = "—"
    if inspection.mechanic_id:
        from sqlalchemy import select
        from app.modules.auth.models import AppUser
        mrow = await db.execute(
            select(AppUser.full_name).where(AppUser.id == inspection.mechanic_id)
        )
        row = mrow.first()
        if row:
            mechanic_name = row[0]

    sections = []
    for section in (inspection.template.sections or []):
        items = []
        for item in section.get("items", []):
            result = results_map.get(item["id"])
            status = result.status.value if result else None
            items.append(
                {
                    "item_id": item["id"],
                    "item_label": item["label"],
                    "item_status": status,
                    "notes": result.notes if result else None,
                    "actionable": status in ("attention", "defective"),
                }
            )
        sections.append(
            {
                "section_id": section.get("id", ""),
                "section_title": section.get("title", ""),
                "items": items,
            }
        )

    return {
        "inspection_id": str(inspection.public_id),
        "template_name": inspection.template.name,
        "vehicle_info": vehicle_info,
        "mechanic_name": mechanic_name,
        "completed_at": inspection.completed_at,
        "sections": sections,
    }
