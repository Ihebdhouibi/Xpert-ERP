"""Repository for AccountingExport CRUD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting_export.models import AccountingExport


class AccountingExportRepository:

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        garage_id: int,
        period_start: str,
        period_end: str,
        format: str,
        exported_by: Optional[int] = None,
    ) -> AccountingExport:
        obj = AccountingExport(
            garage_id=garage_id,
            period_start=period_start,
            period_end=period_end,
            format=format,
            status="pending",
            exported_by=exported_by,
        )
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    @staticmethod
    async def get_by_public_id(
        db: AsyncSession, garage_id: int, public_id: str
    ) -> Optional[AccountingExport]:
        result = await db.execute(
            select(AccountingExport).where(
                AccountingExport.garage_id == garage_id,
                AccountingExport.public_id == public_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        garage_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AccountingExport], int]:
        base = select(AccountingExport).where(AccountingExport.garage_id == garage_id)
        total_result = await db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total: int = total_result.scalar_one()
        rows_result = await db.execute(
            base.order_by(AccountingExport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows_result.scalars().all()), total

    @staticmethod
    async def update(
        db: AsyncSession, obj: AccountingExport, **kwargs
    ) -> AccountingExport:
        for k, v in kwargs.items():
            setattr(obj, k, v)
        obj.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(obj)
        return obj
