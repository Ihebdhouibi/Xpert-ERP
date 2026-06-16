"""Credit note and refund Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.modules.credit_note.models import CreditNoteStatus
from app.modules.payment.models import PaymentMethod


# ---------------------------------------------------------------------------
# Refund schemas (defined first — referenced by CreditNoteOut)
# ---------------------------------------------------------------------------


class RefundCreateRequest(BaseModel):
    payment_id: int
    amount_minor: int = Field(..., ge=1, description="Amount to refund in minor units (cents).")
    payment_method: PaymentMethod = PaymentMethod.cash
    reason: Optional[str] = Field(None, max_length=1000)
    reference: Optional[str] = Field(None, max_length=100)
    credit_note_id: Optional[int] = None


class RefundOut(BaseModel):
    id: int
    garage_id: int
    payment_id: int
    credit_note_id: Optional[int]
    amount_minor: int
    payment_method: PaymentMethod
    reason: Optional[str]
    reference: Optional[str]
    refunded_at: datetime
    created_at: datetime
    created_by: Optional[int]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Credit note schemas
# ---------------------------------------------------------------------------


class CreditNoteCreateRequest(BaseModel):
    invoice_id: int
    total_minor: int = Field(..., ge=1, description="Amount to credit in minor units (cents).")
    reason: Optional[str] = Field(None, max_length=1000)


class CreditNoteOut(BaseModel):
    id: int
    garage_id: int
    invoice_id: int
    doc_number: Optional[str]
    status: CreditNoteStatus
    total_minor: int
    reason: Optional[str]
    issued_at: Optional[datetime]
    voided_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    refunds: list[RefundOut] = []
    # Denormalised invoice fields — populated by service._build_cn_out()
    invoice_doc_number: Optional[str] = None
    invoice_public_id: Optional[str] = None
    invoice_total_minor: int = 0
    invoice_paid_amount_minor: int = 0

    model_config = {"from_attributes": True}


class CreditNoteListResponse(BaseModel):
    items: list[CreditNoteOut]
    total: int
    page: int
    page_size: int
