from __future__ import annotations

import uuid as uuid_lib
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.supplier.models import Supplier, SupplierPartPrice, SupplierStatus


class SupplierRepository:
    @staticmethod
    async def get_by_public_id(
        db: AsyncSession,
        garage_id: int,
        public_id: str,
        include_deleted: bool = False,
    ) -> Optional[Supplier]:
        try:
            uid = uuid_lib.UUID(public_id)
        except (ValueError, AttributeError):
            return None
        stmt = select(Supplier).where(
            Supplier.public_id == uid,
            Supplier.garage_id == garage_id,
        )
        if not include_deleted:
            stmt = stmt.where(Supplier.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        search: Optional[str] = None,
        status: Optional[SupplierStatus] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Supplier], int]:
        stmt = select(Supplier).where(Supplier.garage_id == garage_id)
        if not include_deleted:
            stmt = stmt.where(Supplier.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(Supplier.status == status)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Supplier.name.ilike(pattern),
                    Supplier.email.ilike(pattern),
                    Supplier.phone.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            stmt.order_by(Supplier.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def create(
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
        supplier = Supplier(
            garage_id=garage_id,
            name=name,
            email=email,
            phone=phone,
            address=address,
            payment_terms_days=payment_terms_days,
            average_delivery_days=average_delivery_days,
        )
        db.add(supplier)
        await db.flush()
        return supplier

    @staticmethod
    async def update(
        db: AsyncSession,
        supplier: Supplier,
        submitted_version: int,
        **data,
    ) -> Supplier:
        for key, value in data.items():
            setattr(supplier, key, value)
        supplier.version = submitted_version + 1
        supplier.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return supplier

    @staticmethod
    async def soft_delete(db: AsyncSession, supplier: Supplier) -> None:
        supplier.deleted_at = datetime.now(timezone.utc)
        await db.flush()


class SupplierPartPriceRepository:
    @staticmethod
    async def add_price(
        db: AsyncSession,
        *,
        supplier_id: int,
        part_id: int,
        unit_price_minor: int,
        currency: str,
        effective_from: date,
    ) -> SupplierPartPrice:
        # Close any currently-open price entry for this supplier+part
        open_stmt = select(SupplierPartPrice).where(
            SupplierPartPrice.supplier_id == supplier_id,
            SupplierPartPrice.part_id == part_id,
            SupplierPartPrice.effective_to.is_(None),
        )
        result = await db.execute(open_stmt)
        current = result.scalar_one_or_none()
        if current is not None:
            current.effective_to = effective_from - timedelta(days=1)

        price = SupplierPartPrice(
            supplier_id=supplier_id,
            part_id=part_id,
            unit_price_minor=unit_price_minor,
            currency=currency,
            effective_from=effective_from,
        )
        db.add(price)
        await db.flush()
        return price

    @staticmethod
    async def list_history(
        db: AsyncSession,
        supplier_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple]:
        """Returns rows of (SupplierPartPrice, part_public_id_str, part_name, part_sku)."""
        from app.modules.parts.models import Part

        stmt = (
            select(
                SupplierPartPrice,
                Part.public_id.label("part_public_id"),
                Part.name.label("part_name"),
                Part.sku_code.label("part_sku"),
            )
            .join(Part, SupplierPartPrice.part_id == Part.id)
            .where(SupplierPartPrice.supplier_id == supplier_id)
            .order_by(
                SupplierPartPrice.part_id,
                SupplierPartPrice.effective_from.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [
            (row[0], str(row[1]), row[2], row[3]) for row in result.all()
        ]

    @staticmethod
    async def get_price_at(
        db: AsyncSession,
        supplier_id: int,
        part_id: int,
        at_date: date,
    ) -> Optional[SupplierPartPrice]:
        stmt = (
            select(SupplierPartPrice)
            .where(
                SupplierPartPrice.supplier_id == supplier_id,
                SupplierPartPrice.part_id == part_id,
                SupplierPartPrice.effective_from <= at_date,
                or_(
                    SupplierPartPrice.effective_to.is_(None),
                    SupplierPartPrice.effective_to >= at_date,
                ),
            )
            .order_by(SupplierPartPrice.effective_from.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_comparison_for_part(
        db: AsyncSession,
        garage_id: int,
        part_id: int,
        at_date: Optional[date] = None,
    ) -> list[dict]:
        """All active suppliers with their effective price for this part at at_date."""
        if at_date is None:
            at_date = date.today()

        supplier_stmt = select(Supplier).where(
            Supplier.garage_id == garage_id,
            Supplier.deleted_at.is_(None),
            Supplier.status == SupplierStatus.active,
        )
        suppliers = (await db.execute(supplier_stmt)).scalars().all()

        items: list[dict] = []
        for supplier in suppliers:
            price = await SupplierPartPriceRepository.get_price_at(
                db, supplier.id, part_id, at_date
            )
            if price is None:
                continue
            items.append(
                {
                    "supplier_public_id": str(supplier.public_id),
                    "supplier_name": supplier.name,
                    "average_delivery_days": supplier.average_delivery_days,
                    "reliability_score": (
                        float(supplier.reliability_score)
                        if supplier.reliability_score is not None
                        else None
                    ),
                    "unit_price_minor": price.unit_price_minor,
                    "currency": price.currency,
                    "effective_from": price.effective_from.isoformat(),
                    "effective_to": (
                        price.effective_to.isoformat()
                        if price.effective_to is not None
                        else None
                    ),
                }
            )

        return sorted(items, key=lambda x: x["unit_price_minor"])
