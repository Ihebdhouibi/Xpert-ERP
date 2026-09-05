from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.modules.kpi.export_service import export_csv, export_xlsx
from app.modules.kpi.repository import KpiSnapshotRepository
from app.modules.kpi.schemas import (
    AnalyticsResponse,
    KpiLiveResponse,
    KpiSnapshotOut,
    KpiTrendResponse,
    KpiValueOut,
    OutstandingResponse,
    RevenueResponse,
)
from app.modules.kpi.service import (
    compute_analytics,
    get_live_kpis,
    outstanding_as_of,
    revenue_for_period,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/kpi", tags=["kpi"])
logger = get_logger("kpi.router")


@router.get(
    "/live",
    response_model=KpiLiveResponse,
    dependencies=[require_permission("reporting.dashboard.read")],
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
    dependencies=[require_permission("reporting.dashboard.read")],
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


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    dependencies=[require_permission("reporting.dashboard.read")],
)
async def get_analytics(
    user: AuthUser,
    from_date: date = Query(
        default_factory=lambda: date.today() - timedelta(days=29),
        description="Start date (inclusive)",
    ),
    to_date: date = Query(
        default_factory=date.today,
        description="End date (inclusive)",
    ),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    """Period-scoped analytics: revenue trend, repair count trend, mechanic productivity."""
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be <= to_date")
    data = await compute_analytics(db, user.garage_id, from_date, to_date)
    return AnalyticsResponse(
        from_date=data["from_date"],
        to_date=data["to_date"],
        revenue_trend=[{"date": p["date"], "value": p["value"]} for p in data["revenue_trend"]],
        repair_count_trend=[{"date": p["date"], "value": p["value"]} for p in data["repair_count_trend"]],
        mechanic_productivity=data["mechanic_productivity"],
        outstanding_trend=[{"date": p["date"], "value": p["value"]} for p in data["outstanding_trend"]],
    )


@router.get(
    "/revenue",
    response_model=RevenueResponse,
    dependencies=[require_permission("reporting.dashboard.read")],
)
async def get_revenue(
    user: AuthUser,
    from_date: date = Query(..., description="Start date (inclusive)"),
    to_date: date = Query(..., description="End date (inclusive)"),
    db: AsyncSession = Depends(get_db),
) -> RevenueResponse:
    """Net chiffre d'affaires (paid invoices minus issued avoirs) for an arbitrary date range."""
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be <= to_date")
    value = await revenue_for_period(db, user.garage_id, from_date, to_date)
    return RevenueResponse(from_date=from_date, to_date=to_date, value=float(value))


@router.get(
    "/outstanding",
    response_model=OutstandingResponse,
    dependencies=[require_permission("reporting.dashboard.read")],
)
async def get_outstanding(
    user: AuthUser,
    as_of_date: date = Query(..., description="Balance as of this date (inclusive)"),
    db: AsyncSession = Depends(get_db),
) -> OutstandingResponse:
    """Customer outstanding balance as of a given date, reconstructed from the ledger."""
    value = await outstanding_as_of(db, user.garage_id, as_of_date)
    return OutstandingResponse(as_of_date=as_of_date, value=float(value))


_EXPORT_TABLES = {"top_customers", "top_suppliers", "low_stock_alerts"}
_EXPORT_PERMISSION: dict[str, str] = {
    "top_customers": "reporting.dashboard.read",
    "top_suppliers": "reporting.dashboard.read",
    "low_stock_alerts": "reporting.inventory.read",
}
_EXPORT_FILENAMES: dict[str, str] = {
    "top_customers": "top_clients",
    "top_suppliers": "top_fournisseurs",
    "low_stock_alerts": "alertes_stock",
}


@router.get("/export")
async def export_table(
    user: AuthUser,
    table: str = Query(..., description="Table to export: top_customers | top_suppliers | low_stock_alerts"),
    format: Literal["csv", "xlsx"] = Query("csv", description="Output format"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export a KPI table as CSV or Excel."""
    if table not in _EXPORT_TABLES:
        raise HTTPException(status_code=422, detail=f"Unknown table: {table}")

    required_perm = _EXPORT_PERMISSION[table]
    if not user.has_permission(required_perm):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    filename = _EXPORT_FILENAMES[table]
    if format == "xlsx":
        content = await export_xlsx(db, user.garage_id, table)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )
    else:
        content = await export_csv(db, user.garage_id, table)
        return Response(
            content=content.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
