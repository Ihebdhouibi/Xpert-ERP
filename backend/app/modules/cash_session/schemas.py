"""Cash session Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.modules.cash_session.models import CashSessionStatus
from app.modules.payment.models import PaymentMethod


class OpenSessionRequest(BaseModel):
    pass  # no inputs required; garage + user from auth token


class CloseSessionRequest(BaseModel):
    counted_total_cash: int = Field(..., ge=0, description="Physical cash count in minor units")
    closing_reason: Optional[str] = Field(None, max_length=500)


class PaymentMethodTally(BaseModel):
    payment_method: PaymentMethod
    count: int
    total_minor: int


class ZReportData(BaseModel):
    session_id: int
    garage_id: int
    opened_at: datetime
    closed_at: Optional[datetime]
    opened_by_id: Optional[int]
    closed_by_id: Optional[int]
    tallies: list[PaymentMethodTally]
    expected_total_cash: Optional[int]
    counted_total_cash: Optional[int]
    difference: Optional[int]
    closing_reason: Optional[str]
    total_all_methods: int


class CashSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    garage_id: int
    status: CashSessionStatus
    opened_at: datetime
    opened_by_id: Optional[int]
    closed_at: Optional[datetime]
    closed_by_id: Optional[int]
    expected_total_cash: Optional[int]
    counted_total_cash: Optional[int]
    difference: Optional[int]
    closing_reason: Optional[str]


class CashSessionListResponse(BaseModel):
    items: list[CashSessionOut]
    total: int
    page: int
    page_size: int
