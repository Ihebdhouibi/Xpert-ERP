"""Pydantic schemas for the quotation module."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.quotation.models import LineKind, QuotationStatus


# ---------------------------------------------------------------------------
# Line schemas
# ---------------------------------------------------------------------------

class QuotationLineCreateRequest(BaseModel):
    kind: LineKind = LineKind.service
    part_id: Optional[int] = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price_minor: int = Field(..., ge=0, description="Unit price in minor currency units (e.g. cents)")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)
    vat_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)


class QuotationLineUpdateRequest(BaseModel):
    kind: Optional[LineKind] = None
    part_id: Optional[int] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[Decimal] = Field(None, gt=0, decimal_places=3)
    unit_price_minor: Optional[int] = Field(None, ge=0)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)


class QuotationLineOut(BaseModel):
    id: int
    quotation_id: int
    kind: LineKind
    part_id: Optional[int]
    description: str
    quantity: Decimal
    unit_price_minor: int
    discount_percent: Decimal
    vat_rate: Decimal
    line_total_minor: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Quotation header schemas
# ---------------------------------------------------------------------------

class QuotationCreateRequest(BaseModel):
    customer_id: int
    vehicle_id: Optional[int] = None
    repair_order_id: Optional[int] = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    valid_until: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)
    lines: list[QuotationLineCreateRequest] = Field(default_factory=list)


class QuotationUpdateRequest(BaseModel):
    vehicle_id: Optional[int] = None
    repair_order_id: Optional[int] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    valid_until: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)


class QuotationOut(BaseModel):
    id: int
    public_id: str
    garage_id: int
    customer_id: int
    customer_name: Optional[str] = None
    vehicle_id: Optional[int]
    repair_order_id: Optional[int]
    doc_number: Optional[str]
    status: QuotationStatus
    valid_until: Optional[datetime]
    subtotal_minor: int
    discount_minor: int
    vat_minor: int
    total_minor: int
    currency: str
    notes: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime
    lines: list[QuotationLineOut] = []

    model_config = {"from_attributes": True}


class QuotationListResponse(BaseModel):
    items: list[QuotationOut]
    total: int
    page: int
    page_size: int
