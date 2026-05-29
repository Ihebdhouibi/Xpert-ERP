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
