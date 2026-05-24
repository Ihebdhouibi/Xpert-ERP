from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.parts.models import Part, PartCategory, PartStatus
from app.modules.parts.repository import PartCategoryRepository, PartRepository


class PartNotFoundError(Exception):
    pass


class PartSKUConflictError(Exception):
    def __init__(self, sku_code: str) -> None:
        self.sku_code = sku_code
        super().__init__(f"SKU already exists in this garage: {sku_code}")


class PartVersionConflictError(Exception):
    def __init__(self, current: int, submitted: int) -> None:
        self.current_version = current
        self.submitted_version = submitted
        super().__init__(f"Version conflict: current={current}, submitted={submitted}")


class CategoryNotFoundError(Exception):
    pass


class CategoryHasPartsError(Exception):
    pass


class EquivalentSelfLinkError(Exception):
    pass


class EquivalentAlreadyLinkedError(Exception):
    pass


class EquivalentNotFoundError(Exception):
    pass


# ---------------------------------------------------------------------------
# Category service
# ---------------------------------------------------------------------------

async def create_category(
    db: AsyncSession,
    garage_id: int,
    name: str,
    description: Optional[str],
    parent_id: Optional[int],
) -> PartCategory:
    if parent_id is not None:
        parent = await PartCategoryRepository.get(db, garage_id, parent_id)
        if not parent:
            raise CategoryNotFoundError(f"Parent category {parent_id} not found")
    return await PartCategoryRepository.create(db, garage_id, name, description, parent_id)


async def update_category(
    db: AsyncSession,
    garage_id: int,
    category_id: int,
    name: Optional[str],
    description: Optional[str],
    parent_id: Optional[int],
) -> PartCategory:
    cat = await PartCategoryRepository.get(db, garage_id, category_id)
    if not cat:
        raise CategoryNotFoundError(f"Category {category_id} not found")
    if parent_id is not None and parent_id != category_id:
        parent = await PartCategoryRepository.get(db, garage_id, parent_id)
        if not parent:
            raise CategoryNotFoundError(f"Parent category {parent_id} not found")
    return await PartCategoryRepository.update(db, cat, name, description, parent_id)


async def delete_category(db: AsyncSession, garage_id: int, category_id: int) -> None:
    cat = await PartCategoryRepository.get(db, garage_id, category_id)
    if not cat:
        raise CategoryNotFoundError(f"Category {category_id} not found")
    if await PartCategoryRepository.has_parts(db, category_id):
        raise CategoryHasPartsError("Cannot delete category with active parts")
    await PartCategoryRepository.delete(db, cat)


# ---------------------------------------------------------------------------
# Part service
# ---------------------------------------------------------------------------

async def create_part(
    db: AsyncSession,
    garage_id: int,
    sku_code: str,
    name: str,
    description: Optional[str],
    category_id: Optional[int],
    unit_of_measure: str,
    purchase_price_minor: int,
    selling_price_minor: int,
    supplier_hint_id: Optional[int],
    reorder_threshold: Optional[int],
    reorder_quantity: Optional[int],
    status: PartStatus,
) -> Part:
    existing = await PartRepository.get_by_sku(db, garage_id, sku_code)
    if existing:
        raise PartSKUConflictError(sku_code)
    return await PartRepository.create(
        db,
        garage_id=garage_id,
        sku_code=sku_code.upper(),
        name=name,
        description=description,
        category_id=category_id,
        unit_of_measure=unit_of_measure,
        purchase_price_minor=purchase_price_minor,
        selling_price_minor=selling_price_minor,
        supplier_hint_id=supplier_hint_id,
        reorder_threshold=reorder_threshold,
        reorder_quantity=reorder_quantity,
        status=status,
    )


async def update_part(
    db: AsyncSession,
    garage_id: int,
    public_id: str,
    submitted_version: int,
    **data,
) -> Part:
    part = await PartRepository.get_by_public_id(db, garage_id, public_id)
    if not part:
        raise PartNotFoundError(f"Part {public_id} not found")
    if part.version != submitted_version:
        raise PartVersionConflictError(part.version, submitted_version)
    return await PartRepository.update(db, part, submitted_version, **data)


async def soft_delete_part(db: AsyncSession, garage_id: int, public_id: str) -> None:
    part = await PartRepository.get_by_public_id(db, garage_id, public_id)
    if not part:
        raise PartNotFoundError(f"Part {public_id} not found")
    await PartRepository.soft_delete(db, part)


# ---------------------------------------------------------------------------
# Equivalent service
# ---------------------------------------------------------------------------

async def link_equivalents(
    db: AsyncSession,
    garage_id: int,
    public_id_a: str,
    public_id_b: str,
) -> None:
    if public_id_a == public_id_b:
        raise EquivalentSelfLinkError("A part cannot be equivalent to itself")
    part_a = await PartRepository.get_by_public_id(db, garage_id, public_id_a)
    if not part_a:
        raise PartNotFoundError(f"Part {public_id_a} not found")
    part_b = await PartRepository.get_by_public_id(db, garage_id, public_id_b)
    if not part_b:
        raise PartNotFoundError(f"Part {public_id_b} not found")
    existing = await PartRepository.get_equivalent_link(db, part_a.id, part_b.id)
    if existing:
        raise EquivalentAlreadyLinkedError("Parts are already linked as equivalents")
    await PartRepository.add_equivalent(db, part_a.id, part_b.id)


async def unlink_equivalents(
    db: AsyncSession,
    garage_id: int,
    public_id_a: str,
    public_id_b: str,
) -> None:
    part_a = await PartRepository.get_by_public_id(db, garage_id, public_id_a)
    if not part_a:
        raise PartNotFoundError(f"Part {public_id_a} not found")
    part_b = await PartRepository.get_by_public_id(db, garage_id, public_id_b)
    if not part_b:
        raise PartNotFoundError(f"Part {public_id_b} not found")
    link = await PartRepository.get_equivalent_link(db, part_a.id, part_b.id)
    if not link:
        raise EquivalentNotFoundError("No equivalence link exists between these parts")
    await PartRepository.remove_equivalent(db, part_a.id, part_b.id)
