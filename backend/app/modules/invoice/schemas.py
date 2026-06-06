"""Pydantic schemas for the invoice module."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.modules.invoice.models import InvoiceLineKind, InvoiceStatus


# ---------------------------------------------------------------------------
# Line schemas
# ---------------------------------------------------------------------------

class InvoiceLineCreateRequest(BaseModel):
    kind: InvoiceLineKind = InvoiceLineKind.service
    part_id: Optional[int] = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price_minor: int = Field(..., ge=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)
    vat_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)


class InvoiceLineUpdateRequest(BaseModel):
    kind: Optional[InvoiceLineKind] = None
    part_id: Optional[int] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[Decimal] = Field(None, gt=0, decimal_places=3)
    unit_price_minor: Optional[int] = Field(None, ge=0)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)


class InvoiceLineOut(BaseModel):
    id: int
    invoice_id: int
    kind: InvoiceLineKind
    part_id: Optional[int]
    description: str
    quantity: Decimal
    unit_price_minor: int
    discount_percent: Decimal
    vat_rate: Decimal
    line_total_minor: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Invoice schemas
# ---------------------------------------------------------------------------

class InvoiceCreateRequest(BaseModel):
    customer_id: int
    vehicle_id: Optional[int] = None
    repair_order_id: Optional[int] = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    due_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)
    lines: list[InvoiceLineCreateRequest] = Field(default_factory=list)


class InvoiceUpdateRequest(BaseModel):
    vehicle_id: Optional[int] = None
    repair_order_id: Optional[int] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    due_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)


class InvoiceOut(BaseModel):
    id: int
    public_id: str
    garage_id: int
    customer_id: int
    customer_name: Optional[str] = None
    vehicle_id: Optional[int]
    repair_order_id: Optional[int]
    quotation_id: Optional[int]
    doc_number: Optional[str]
    status: InvoiceStatus
    issued_at: Optional[datetime]
    due_at: Optional[datetime]
    subtotal_minor: int
    discount_minor: int
    vat_minor: int
    total_minor: int
    paid_amount_minor: int
    outstanding_minor: int
    currency: str
    is_exported: bool
    notes: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineOut] = []

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    items: list[InvoiceOut]
    total: int
    page: int
    page_size: int
