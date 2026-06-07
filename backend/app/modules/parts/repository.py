from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.parts.models import Part, PartCategory, PartEquivalent, PartStatus
from app.modules.parts.stock_models import StockLevel


class PartCategoryRepository:
    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        parent_id: Optional[int] = None,
        flat: bool = False,
    ) -> list[PartCategory]:
        stmt = select(PartCategory).where(PartCategory.garage_id == garage_id)
        if not flat:
            if parent_id is None:
                stmt = stmt.where(PartCategory.parent_id.is_(None))
            else:
                stmt = stmt.where(PartCategory.parent_id == parent_id)
        stmt = stmt.order_by(PartCategory.name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, garage_id: int, category_id: int) -> Optional[PartCategory]:
        result = await db.execute(
            select(PartCategory).where(
                PartCategory.id == category_id,
                PartCategory.garage_id == garage_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        garage_id: int,
        name: str,
        description: Optional[str],
        parent_id: Optional[int],
    ) -> PartCategory:
        cat = PartCategory(
            garage_id=garage_id,
            name=name,
            description=description,
            parent_id=parent_id,
        )
        db.add(cat)
        await db.flush()
        return cat

    @staticmethod
    async def update(
        db: AsyncSession,
        cat: PartCategory,
        name: Optional[str],
        description: Optional[str],
        parent_id: Optional[int],
    ) -> PartCategory:
        if name is not None:
            cat.name = name
        if description is not None:
            cat.description = description
        if parent_id is not None:
            cat.parent_id = parent_id
        cat.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return cat

    @staticmethod
    async def has_parts(db: AsyncSession, category_id: int) -> bool:
        result = await db.execute(
            select(func.count(Part.id)).where(
                Part.category_id == category_id,
                Part.deleted_at.is_(None),
            )
        )
        return (result.scalar() or 0) > 0

    @staticmethod
    async def delete(db: AsyncSession, cat: PartCategory) -> None:
        await db.delete(cat)
        await db.flush()


class PartRepository:
    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        status: Optional[PartStatus] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[Part, int]], int]:
        stmt = (
            select(Part, func.coalesce(StockLevel.on_hand, 0).label("on_hand"))
            .outerjoin(StockLevel, (StockLevel.part_id == Part.id) & (StockLevel.garage_id == Part.garage_id))
            .where(Part.garage_id == garage_id)
        )

        if not include_deleted:
            stmt = stmt.where(Part.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(Part.status == status)
        if category_id is not None:
            stmt = stmt.where(Part.category_id == category_id)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(Part.name.ilike(pattern), Part.sku_code.ilike(pattern))
            )

        count_stmt = select(func.count()).select_from(
            select(Part)
            .where(Part.garage_id == garage_id)
            .where(Part.deleted_at.is_(None) if not include_deleted else True)
            .subquery()
        )
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(Part.name).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return [(row.Part, row.on_hand) for row in result.mappings()], total

    @staticmethod
    async def get_by_public_id(
        db: AsyncSession,
        garage_id: int,
        public_id: str,
        include_deleted: bool = False,
        load_category: bool = False,
    ) -> Optional[Part]:
        try:
            uid = uuid_lib.UUID(public_id)
        except (ValueError, AttributeError):
            return None

        stmt = select(Part).where(
            Part.public_id == uid,
            Part.garage_id == garage_id,
        )
        if not include_deleted:
            stmt = stmt.where(Part.deleted_at.is_(None))
        if load_category:
            stmt = stmt.options(selectinload(Part.category))

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_sku(
        db: AsyncSession, garage_id: int, sku_code: str
    ) -> Optional[Part]:
        result = await db.execute(
            select(Part).where(
                Part.garage_id == garage_id,
                Part.sku_code == sku_code.upper(),
                Part.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, garage_id: int, **data) -> Part:
        part = Part(garage_id=garage_id, **data)
        db.add(part)
        await db.flush()
        return part

    @staticmethod
    async def update(
        db: AsyncSession,
        part: Part,
        submitted_version: int,
        **data,
    ) -> Part:
        for key, value in data.items():
            if value is not None:
                setattr(part, key, value)
        part.updated_at = datetime.now(timezone.utc)
        part.version = submitted_version + 1
        await db.flush()
        return part

    @staticmethod
    async def soft_delete(db: AsyncSession, part: Part) -> None:
        part.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    # ------------------------------------------------------------------
    # Equivalents  (bidirectional, normalised as a < b)
    # ------------------------------------------------------------------

    @staticmethod
    def _ordered(a: int, b: int) -> tuple[int, int]:
        return (a, b) if a < b else (b, a)

    @staticmethod
    async def get_equivalents(db: AsyncSession, part_id: int) -> list[Part]:
        """Return all parts equivalent to part_id (resolves both sides)."""
        links_a = await db.execute(
            select(PartEquivalent.part_b_id).where(PartEquivalent.part_a_id == part_id)
        )
        links_b = await db.execute(
            select(PartEquivalent.part_a_id).where(PartEquivalent.part_b_id == part_id)
        )
        peer_ids = {row[0] for row in links_a} | {row[0] for row in links_b}
        if not peer_ids:
            return []
        result = await db.execute(
            select(Part).where(Part.id.in_(peer_ids), Part.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_equivalent_link(
        db: AsyncSession, part_a_id: int, part_b_id: int
    ) -> Optional[PartEquivalent]:
        lo, hi = PartRepository._ordered(part_a_id, part_b_id)
        result = await db.execute(
            select(PartEquivalent).where(
                PartEquivalent.part_a_id == lo,
                PartEquivalent.part_b_id == hi,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def add_equivalent(
        db: AsyncSession, part_a_id: int, part_b_id: int
    ) -> PartEquivalent:
        lo, hi = PartRepository._ordered(part_a_id, part_b_id)
        link = PartEquivalent(part_a_id=lo, part_b_id=hi)
        db.add(link)
        await db.flush()
        return link

    @staticmethod
    async def remove_equivalent(
        db: AsyncSession, part_a_id: int, part_b_id: int
    ) -> None:
        lo, hi = PartRepository._ordered(part_a_id, part_b_id)
        link = await PartRepository.get_equivalent_link(db, lo, hi)
        if link:
            await db.delete(link)
            await db.flush()
