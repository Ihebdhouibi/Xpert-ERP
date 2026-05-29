from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


class KpiValueOut(BaseModel):
    value: Optional[float]
    meta: Optional[Any] = None


class KpiLiveResponse(BaseModel):
    garage_id: int
    computed_at: datetime
    refresh_interval_seconds: int
    kpis: dict[str, KpiValueOut]


class KpiSnapshotOut(BaseModel):
    id: int
    garage_id: int
    snapshot_date: date
    kpi_code: str
    value: Optional[Decimal]
    meta: Optional[Any]
    computed_at: datetime

    model_config = {"from_attributes": True}


class KpiTrendResponse(BaseModel):
    kpi_code: str
    from_date: date
    to_date: date
    points: list[KpiSnapshotOut]


class AnalyticsTrendPoint(BaseModel):
    date: str
    value: float


class MechanicProductivityEntry(BaseModel):
    name: str
    completed_count: int
    avg_duration_h: Optional[float]


class AnalyticsResponse(BaseModel):
    from_date: str
    to_date: str
    revenue_trend: list[AnalyticsTrendPoint]
    repair_count_trend: list[AnalyticsTrendPoint]
    mechanic_productivity: list[MechanicProductivityEntry]
