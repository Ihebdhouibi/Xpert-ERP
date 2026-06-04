from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.supplier.models import Supplier, SupplierPartPrice
from app.modules.supplier.repository import SupplierPartPriceRepository, SupplierRepository

logger = get_logger("supplier.service")


class SupplierNotFoundError(Exception):
    def __init__(self, public_id: str) -> None:
        self.public_id = public_id
        super().__init__(f"Supplier not found: {public_id}")


class SupplierVersionConflictError(Exception):
    def __init__(self, current: int, submitted: int) -> None:
        self.current_version = current
        self.submitted_version = submitted
        super().__init__(
            f"Version conflict: current={current}, submitted={submitted}"
        )


class PartNotFoundForPriceError(Exception):
    def __init__(self, part_public_id: str) -> None:
        self.part_public_id = part_public_id
        super().__init__(f"Part not found: {part_public_id}")


async def create_supplier(
    db: AsyncSession,
    *,
    garage_id: int,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    payment_terms_days: Optional[int] = None,
    average_delivery_days: Optional[int] = None,
) -> Supplier:
    logger.info("create_supplier_start", garage_id=garage_id, name=name)
    supplier = await SupplierRepository.create(
        db,
        garage_id=garage_id,
        name=name,
        email=email,
        phone=phone,
        address=address,
        payment_terms_days=payment_terms_days,
        average_delivery_days=average_delivery_days,
    )
    logger.info("supplier_created", supplier_public_id=str(supplier.public_id), name=name, garage_id=garage_id)
    return supplier


async def update_supplier(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
    submitted_version: int,
    **data,
) -> Supplier:
    logger.info("update_supplier_start", public_id=public_id, garage_id=garage_id)
    supplier = await SupplierRepository.get_by_public_id(db, garage_id, public_id)
    if not supplier:
        raise SupplierNotFoundError(public_id)
    if supplier.version != submitted_version:
        raise SupplierVersionConflictError(supplier.version, submitted_version)
    result = await SupplierRepository.update(db, supplier, submitted_version, **data)
    logger.info("update_supplier_success", public_id=public_id, garage_id=garage_id)
    return result


async def delete_supplier(
    db: AsyncSession,
    *,
    garage_id: int,
    public_id: str,
) -> None:
    logger.info("delete_supplier_start", public_id=public_id, garage_id=garage_id)
    supplier = await SupplierRepository.get_by_public_id(db, garage_id, public_id)
    if not supplier:
        raise SupplierNotFoundError(public_id)
    await SupplierRepository.soft_delete(db, supplier)
    logger.info("delete_supplier_success", public_id=public_id, garage_id=garage_id)


async def add_supplier_price(
    db: AsyncSession,
    *,
    garage_id: int,
    supplier_public_id: str,
    part_public_id: str,
    unit_price_minor: int,
    currency: str,
    effective_from: date,
) -> SupplierPartPrice:
    logger.info("add_supplier_price_start", supplier_public_id=supplier_public_id, part_public_id=part_public_id, garage_id=garage_id)
    from app.modules.parts.repository import PartRepository

    supplier = await SupplierRepository.get_by_public_id(db, garage_id, supplier_public_id)
    if not supplier:
        raise SupplierNotFoundError(supplier_public_id)

    part = await PartRepository.get_by_public_id(db, garage_id, part_public_id)
    if not part:
        raise PartNotFoundForPriceError(part_public_id)

    result = await SupplierPartPriceRepository.add_price(
        db,
        supplier_id=supplier.id,
        part_id=part.id,
        unit_price_minor=unit_price_minor,
        currency=currency,
        effective_from=effective_from,
    )
    logger.info("add_supplier_price_success", supplier_public_id=supplier_public_id, part_public_id=part_public_id, garage_id=garage_id)
    return result


async def get_part_price_comparison(
    db: AsyncSession,
    *,
    garage_id: int,
    part_public_id: str,
    at_date: Optional[date] = None,
) -> list[dict]:
    logger.info("get_part_price_comparison_start", part_public_id=part_public_id, garage_id=garage_id)
    from app.modules.parts.repository import PartRepository

    part = await PartRepository.get_by_public_id(db, garage_id, part_public_id)
    if not part:
        raise PartNotFoundForPriceError(part_public_id)

    result = await SupplierPartPriceRepository.get_comparison_for_part(
        db, garage_id, part.id, at_date
    )
    logger.info("get_part_price_comparison_success", part_public_id=part_public_id, count=len(result), garage_id=garage_id)
    return result
