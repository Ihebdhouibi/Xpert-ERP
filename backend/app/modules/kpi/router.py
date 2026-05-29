from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.kpi.repository import KpiSnapshotRepository
from app.modules.kpi.schemas import KpiLiveResponse, KpiSnapshotOut, KpiTrendResponse, KpiValueOut
from app.modules.kpi.service import get_live_kpis

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get(
    "/live",
    response_model=KpiLiveResponse,
    dependencies=[Depends(require_permission("reporting.dashboard.read"))],
)
async def get_live(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> KpiLiveResponse:
    """Return all live KPIs for the authenticated user's garage (Redis-cached)."""
    payload = await get_live_kpis(db, user.garage_id)
    return KpiLiveResponse(
        garage_id=payload["garage_id"],
        computed_at=payload["computed_at"],
        refresh_interval_seconds=payload["refresh_interval_seconds"],
        kpis={
            code: KpiValueOut(value=v["value"], meta=v.get("meta"))
            for code, v in payload["kpis"].items()
        },
    )


@router.get(
    "/snapshots",
    response_model=KpiTrendResponse,
    dependencies=[Depends(require_permission("reporting.dashboard.read"))],
)
async def get_trend(
    user: AuthUser,
    kpi_code: str = Query(..., description="KPI code to fetch trend for"),
    from_date: date = Query(
        default_factory=lambda: date.today() - timedelta(days=29),
        description="Start date (inclusive), defaults to 30 days ago",
    ),
    to_date: date = Query(
        default_factory=date.today,
        description="End date (inclusive), defaults to today",
    ),
    db: AsyncSession = Depends(get_db),
) -> KpiTrendResponse:
    """Return daily KPI snapshots for trend charts over an arbitrary date range."""
    snapshots = await KpiSnapshotRepository.get_trend(
        db,
        garage_id=user.garage_id,
        kpi_code=kpi_code,
        from_date=from_date,
        to_date=to_date,
    )
    return KpiTrendResponse(
        kpi_code=kpi_code,
        from_date=from_date,
        to_date=to_date,
        points=[KpiSnapshotOut.model_validate(s) for s in snapshots],
    )
