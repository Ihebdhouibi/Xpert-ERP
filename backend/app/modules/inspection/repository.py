from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.inspection.models import (
    Inspection,
    InspectionApprovalToken,
    InspectionConflictLog,
    InspectionItemResult,
    InspectionItemStatus,
    InspectionStatus,
    InspectionTemplate,
    VehicleRecommendation,
)


class InspectionTemplateRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        garage_id: int,
        name: str,
        sections: list,
        created_by_user_id: Optional[int] = None,
    ) -> InspectionTemplate:
        template = InspectionTemplate(
            public_id=uuid_lib.uuid4(),
            garage_id=garage_id,
            name=name,
            sections=sections,
            created_by_user_id=created_by_user_id,
        )
        db.add(template)
        await db.flush()
        await db.refresh(template)
        return template

    @staticmethod
    async def list(
        db: AsyncSession,
        *,
        garage_id: int,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InspectionTemplate], int]:
        q = select(InspectionTemplate).where(InspectionTemplate.garage_id == garage_id)
        if not include_deleted:
            q = q.where(InspectionTemplate.deleted_at.is_(None))
        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar_one()
        rows = (
            await db.execute(
                q.order_by(InspectionTemplate.name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_by_public_id(
        db: AsyncSession,
        garage_id: int,
        public_id: str,
        include_deleted: bool = False,
    ) -> Optional[InspectionTemplate]:
        try:
            uid = uuid_lib.UUID(public_id)
        except (ValueError, AttributeError):
            return None
        q = select(InspectionTemplate).where(
            InspectionTemplate.public_id == uid,
            InspectionTemplate.garage_id == garage_id,
        )
        if not include_deleted:
            q = q.where(InspectionTemplate.deleted_at.is_(None))
        return (await db.execute(q)).scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession,
        template: InspectionTemplate,
        *,
        name: Optional[str] = None,
        sections: Optional[list] = None,
    ) -> InspectionTemplate:
        if name is not None:
            template.name = name
        if sections is not None:
            template.sections = sections
        template.version += 1
        template.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(template)
        return template

    @staticmethod
    async def soft_delete(db: AsyncSession, template: InspectionTemplate) -> None:
        template.deleted_at = datetime.now(timezone.utc)
        await db.flush()


class InspectionRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        garage_id: int,
        template_id: int,
        mechanic_id: Optional[int] = None,
        repair_order_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
    ) -> Inspection:
        inspection = Inspection(
            public_id=uuid_lib.uuid4(),
            garage_id=garage_id,
            template_id=template_id,
            mechanic_id=mechanic_id,
            repair_order_id=repair_order_id,
            vehicle_id=vehicle_id,
            status=InspectionStatus.draft,
            created_by_user_id=created_by_user_id,
        )
        db.add(inspection)
        await db.flush()
        await db.refresh(inspection)
        return inspection

    @staticmethod
    async def list(
        db: AsyncSession,
        *,
        garage_id: int,
        status: Optional[InspectionStatus] = None,
        mechanic_id: Optional[int] = None,
        repair_order_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Inspection], int]:
        q = select(Inspection).where(Inspection.garage_id == garage_id)
        if status:
            q = q.where(Inspection.status == status)
        if mechanic_id:
            q = q.where(Inspection.mechanic_id == mechanic_id)
        if repair_order_id:
            q = q.where(Inspection.repair_order_id == repair_order_id)
        if vehicle_id:
            q = q.where(Inspection.vehicle_id == vehicle_id)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar_one()
        rows = (
            await db.execute(
                q.options(selectinload(Inspection.template))
                .order_by(Inspection.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_by_public_id(
        db: AsyncSession,
        garage_id: int,
        public_id: str,
        load_results: bool = False,
    ) -> Optional[Inspection]:
        try:
            uid = uuid_lib.UUID(public_id)
        except (ValueError, AttributeError):
            return None
        q = select(Inspection).where(
            Inspection.public_id == uid,
            Inspection.garage_id == garage_id,
        )
        if load_results:
            q = q.options(
                selectinload(Inspection.results),
                selectinload(Inspection.template),
            )
        return (await db.execute(q)).scalar_one_or_none()

    @staticmethod
    async def transition_status(
        db: AsyncSession,
        inspection: Inspection,
        new_status: InspectionStatus,
    ) -> None:
        now = datetime.now(timezone.utc)
        inspection.status = new_status
        inspection.updated_at = now
        inspection.version += 1
        if new_status == InspectionStatus.in_progress and inspection.started_at is None:
            inspection.started_at = now
        if new_status == InspectionStatus.completed:
            inspection.completed_at = now
        await db.flush()

    @staticmethod
    async def bulk_upsert_results(
        db: AsyncSession,
        inspection: Inspection,
        items: list[dict],
    ) -> list[InspectionConflictLog]:
        """Last-write-wins per item keyed by written_at timestamp."""
        now = datetime.now(timezone.utc)
        conflicts: list[InspectionConflictLog] = []

        q = select(InspectionItemResult).where(
            InspectionItemResult.inspection_id == inspection.id
        )
        existing_rows = (await db.execute(q)).scalars().all()
        existing_map = {r.item_id: r for r in existing_rows}

        for item in items:
            item_id = item["item_id"]
            client_written_at: datetime = item.get("written_at") or now
            if client_written_at.tzinfo is None:
                client_written_at = client_written_at.replace(tzinfo=timezone.utc)
            new_status = InspectionItemStatus(item["status"])
            notes = item.get("notes")
            media_ids = item.get("media_ids") or []

            existing = existing_map.get(item_id)
            if existing is not None:
                server_written_at = existing.written_at
                if server_written_at.tzinfo is None:
                    server_written_at = server_written_at.replace(tzinfo=timezone.utc)
                if client_written_at > server_written_at:
                    existing.status = new_status
                    existing.notes = notes
                    existing.media_ids = media_ids
                    existing.written_at = client_written_at
                    existing.updated_at = now
                else:
                    conflict = InspectionConflictLog(
                        inspection_id=inspection.id,
                        item_id=item_id,
                        client_written_at=client_written_at,
                        server_written_at=server_written_at,
                        discarded_status=new_status.value,
                        kept_status=existing.status.value,
                    )
                    db.add(conflict)
                    conflicts.append(conflict)
            else:
                result = InspectionItemResult(
                    inspection_id=inspection.id,
                    item_id=item_id,
                    status=new_status,
                    notes=notes,
                    media_ids=media_ids,
                    written_at=client_written_at,
                )
                db.add(result)
                existing_map[item_id] = result

        inspection.updated_at = now
        inspection.version += 1
        await db.flush()
        return conflicts

    @staticmethod
    async def set_repair_order(
        db: AsyncSession,
        inspection: Inspection,
        repair_order_id: int,
    ) -> None:
        inspection.repair_order_id = repair_order_id
        inspection.updated_at = datetime.now(timezone.utc)
        inspection.version += 1
        await db.flush()

    @staticmethod
    async def get_by_public_id_any_garage(
        db: AsyncSession,
        public_id: str,
        load_results: bool = False,
    ) -> Optional[Inspection]:
        """Fetch inspection without garage scope — used only for public approval endpoints."""
        try:
            uid = uuid_lib.UUID(public_id)
        except (ValueError, AttributeError):
            return None
        q = select(Inspection).where(Inspection.public_id == uid)
        if load_results:
            q = q.options(
                selectinload(Inspection.results),
                selectinload(Inspection.template),
            )
        return (await db.execute(q)).scalar_one_or_none()


class VehicleRecommendationRepository:
    @staticmethod
    async def create_bulk(
        db: AsyncSession,
        *,
        garage_id: int,
        vehicle_id: int,
        source_inspection_id: int,
        recommendations: list[dict],
        created_by_user_id: Optional[int] = None,
    ) -> list[VehicleRecommendation]:
        created = []
        for rec in recommendations:
            r = VehicleRecommendation(
                public_id=uuid_lib.uuid4(),
                garage_id=garage_id,
                vehicle_id=vehicle_id,
                source_inspection_id=source_inspection_id,
                item_id=rec["item_id"],
                item_label=rec["item_label"],
                item_status=rec["item_status"],
                status="archived",
                notes=rec.get("notes"),
                created_by_user_id=created_by_user_id,
            )
            db.add(r)
            created.append(r)
        await db.flush()
        return created

    @staticmethod
    async def list_for_vehicle(
        db: AsyncSession,
        garage_id: int,
        vehicle_id: int,
    ) -> list[VehicleRecommendation]:
        q = (
            select(VehicleRecommendation)
            .where(
                VehicleRecommendation.garage_id == garage_id,
                VehicleRecommendation.vehicle_id == vehicle_id,
            )
            .order_by(VehicleRecommendation.created_at.desc())
        )
        return list((await db.execute(q)).scalars().all())


class ApprovalTokenRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        jti: str,
        inspection_id: int,
        expires_at: datetime,
    ) -> InspectionApprovalToken:
        token = InspectionApprovalToken(
            jti=jti,
            inspection_id=inspection_id,
            expires_at=expires_at,
        )
        db.add(token)
        await db.flush()
        return token

    @staticmethod
    async def get_by_jti(
        db: AsyncSession, jti: str
    ) -> Optional[InspectionApprovalToken]:
        q = select(InspectionApprovalToken).where(InspectionApprovalToken.jti == jti)
        return (await db.execute(q)).scalar_one_or_none()

    @staticmethod
    async def mark_used(
        db: AsyncSession, token: InspectionApprovalToken
    ) -> None:
        token.used_at = datetime.now(timezone.utc)
        await db.flush()
