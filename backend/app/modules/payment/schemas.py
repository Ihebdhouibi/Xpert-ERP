"""Payment Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.modules.payment.models import PaymentMethod


class PaymentCreateRequest(BaseModel):
    invoice_id: int
    amount_minor: int = Field(..., gt=0, description="Amount in minor currency units (cents)")
    payment_method: PaymentMethod = PaymentMethod.cash
    paid_at: Optional[datetime] = None
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class PaymentOut(BaseModel):
    id: int
    invoice_id: int
    garage_id: int
    amount_minor: int
    payment_method: PaymentMethod
    paid_at: datetime
    reference: Optional[str]
    notes: Optional[str]
    cash_session_id: Optional[int] = None
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
