"""Cash session Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.modules.cash_session.models import CashSessionStatus
from app.modules.payment.models import PaymentMethod


class OpenSessionRequest(BaseModel):
    opening_float: int = Field(
        0, ge=0, description="Cash float in the drawer at open time, in minor units"
    )


class CloseSessionRequest(BaseModel):
    counted_total_cash: int = Field(..., ge=0, description="Physical cash count in minor units")
    closing_reason: Optional[str] = Field(None, max_length=500)


class PaymentMethodTally(BaseModel):
    payment_method: PaymentMethod
    count: int
    total_minor: int


class SessionPaymentOut(BaseModel):
    """A single payment enriched with invoice and customer context for the session detail view."""
    id: int
    paid_at: datetime
    amount_minor: int
    payment_method: PaymentMethod
    reference: Optional[str]
    notes: Optional[str]
    invoice_id: int
    invoice_number: Optional[str]
    customer_name: Optional[str]
    created_by_name: Optional[str]


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
    opening_float: int = 0
    expected_total_cash: Optional[int]
    counted_total_cash: Optional[int]
    difference: Optional[int]
    closing_reason: Optional[str]
    # opening_float + cash payments so far; live value for open sessions, the
    # stored expected_total_cash for closed ones. Lets the UI show the expected
    # drawer amount before the session is closed.
    expected_cash_so_far: Optional[int] = None


class CashSessionListResponse(BaseModel):
    items: list[CashSessionOut]
    total: int
    page: int
    page_size: int
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
    opening_float: int = 0
    expected_total_cash: Optional[int]
    counted_total_cash: Optional[int]
    difference: Optional[int]
    closing_reason: Optional[str]
    # opening_float + cash payments so far; live value for open sessions, the
    # stored expected_total_cash for closed ones. Lets the UI show the expected
    # drawer amount before the session is closed.
    expected_cash_so_far: Optional[int] = None


class CashSessionListResponse(BaseModel):
    items: list[CashSessionOut]
    total: int
    page: int
    page_size: int
