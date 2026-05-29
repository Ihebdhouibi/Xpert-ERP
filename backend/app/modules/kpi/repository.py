from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.kpi.models import KpiSnapshot


class KpiSnapshotRepository:

    @staticmethod
    async def upsert(
        db: AsyncSession,
        *,
        garage_id: int,
        snapshot_date: date,
        kpi_code: str,
        value: Optional[Decimal],
        meta: Optional[Any] = None,
    ) -> KpiSnapshot:
        stmt = (
            pg_insert(KpiSnapshot)
            .values(
                garage_id=garage_id,
                snapshot_date=snapshot_date,
                kpi_code=kpi_code,
                value=value,
                meta=meta,
                computed_at=datetime.now(tz=timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_kpi_snapshot_garage_date_code",
                set_={
                    "value": value,
                    "meta": meta,
                    "computed_at": datetime.now(tz=timezone.utc),
                },
            )
            .returning(KpiSnapshot)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one()

    @staticmethod
    async def upsert_many(
        db: AsyncSession,
        *,
        garage_id: int,
        snapshot_date: date,
        kpis: dict[str, tuple[Optional[Decimal], Optional[Any]]],
    ) -> None:
        """Bulk upsert multiple KPI codes for one garage+date in a single round-trip."""
        now = datetime.now(tz=timezone.utc)
        rows = [
            {
                "garage_id": garage_id,
                "snapshot_date": snapshot_date,
                "kpi_code": code,
                "value": val,
                "meta": meta,
                "computed_at": now,
            }
            for code, (val, meta) in kpis.items()
        ]
        stmt = (
            pg_insert(KpiSnapshot)
            .values(rows)
            .on_conflict_do_update(
                constraint="uq_kpi_snapshot_garage_date_code",
                set_={
                    "value": pg_insert(KpiSnapshot).excluded.value,
                    "meta": pg_insert(KpiSnapshot).excluded.meta,
                    "computed_at": now,
                },
            )
        )
        await db.execute(stmt)
        await db.commit()

    @staticmethod
    async def get_trend(
        db: AsyncSession,
        *,
        garage_id: int,
        kpi_code: str,
        from_date: date,
        to_date: date,
    ) -> list[KpiSnapshot]:
        result = await db.execute(
            select(KpiSnapshot)
            .where(
                KpiSnapshot.garage_id == garage_id,
                KpiSnapshot.kpi_code == kpi_code,
                KpiSnapshot.snapshot_date >= from_date,
                KpiSnapshot.snapshot_date <= to_date,
            )
            .order_by(KpiSnapshot.snapshot_date)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_latest_all(
        db: AsyncSession,
        *,
        garage_id: int,
        snapshot_date: date,
    ) -> list[KpiSnapshot]:
        """All KPI rows for a given garage and snapshot date."""
        result = await db.execute(
            select(KpiSnapshot)
            .where(
                KpiSnapshot.garage_id == garage_id,
                KpiSnapshot.snapshot_date == snapshot_date,
            )
        )
        return list(result.scalars().all())
