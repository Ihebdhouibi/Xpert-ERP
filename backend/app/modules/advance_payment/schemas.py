"""Advance payment Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.modules.payment.models import PaymentMethod


class AdvancePaymentCreateRequest(BaseModel):
    customer_id: int = Field(..., gt=0)
    repair_order_id: Optional[int] = Field(None, gt=0)
    amount_minor: int = Field(..., gt=0, description="Deposit amount in minor units (cents)")
    payment_method: PaymentMethod = PaymentMethod.cash
    paid_at: Optional[datetime] = None
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class AdvancePaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    garage_id: int
    customer_id: int
    repair_order_id: Optional[int]
    amount_minor: int
    payment_method: PaymentMethod
    paid_at: datetime
    reference: Optional[str]
    notes: Optional[str]
    applied_to_invoice_id: Optional[int]
    applied_at: Optional[datetime]
    applied_amount_minor: Optional[int]
    created_by: Optional[int]
    created_at: datetime


class AdvancePaymentListResponse(BaseModel):
    items: list[AdvancePaymentOut]
    total: int
