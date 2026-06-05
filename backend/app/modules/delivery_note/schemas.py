"""Pydantic schemas for the Delivery Note module."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.delivery_note.models import DeliveryNoteLineKind, DeliveryNoteStatus


# ---------------------------------------------------------------------------
# Line schemas
# ---------------------------------------------------------------------------

class DeliveryNoteLineCreateRequest(BaseModel):
    kind: DeliveryNoteLineKind = DeliveryNoteLineKind.part
    part_id: Optional[int] = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price_minor: int = Field(..., ge=0)
    vat_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)


class DeliveryNoteLineUpdateRequest(BaseModel):
    kind: Optional[DeliveryNoteLineKind] = None
    part_id: Optional[int] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[Decimal] = Field(None, gt=0, decimal_places=3)
    unit_price_minor: Optional[int] = Field(None, ge=0)
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)


class DeliveryNoteLineOut(BaseModel):
    id: int
    delivery_note_id: int
    kind: DeliveryNoteLineKind
    part_id: Optional[int]
    description: str
    quantity: Decimal
    unit_price_minor: int
    vat_rate: Decimal
    line_total_minor: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Delivery note header schemas
# ---------------------------------------------------------------------------

class DeliveryNoteCreateRequest(BaseModel):
    customer_id: int
    vehicle_id: Optional[int] = None
    currency: str = Field(default="TND", min_length=3, max_length=3)
    notes: Optional[str] = Field(None, max_length=2000)
    lines: list[DeliveryNoteLineCreateRequest] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if not v.isupper() or len(v) != 3:
            raise ValueError("Currency must be 3 uppercase letters (ISO 4217)")
        return v


class DeliveryNoteUpdateRequest(BaseModel):
    vehicle_id: Optional[int] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v.isupper() or len(v) != 3):
            raise ValueError("Currency must be 3 uppercase letters (ISO 4217)")
        return v


class DeliveryNoteOut(BaseModel):
    id: int
    public_id: str
    garage_id: int
    customer_id: int
    vehicle_id: Optional[int]
    invoice_id: Optional[int]
    doc_number: Optional[str]
    status: DeliveryNoteStatus
    issued_at: Optional[datetime]
    delivered_at: Optional[datetime]
    subtotal_minor: int
    vat_minor: int
    total_minor: int
    currency: str
    notes: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime
    lines: list[DeliveryNoteLineOut] = []

    model_config = {"from_attributes": True}


class DeliveryNoteListResponse(BaseModel):
    items: list[DeliveryNoteOut]
    total: int
    page: int
    page_size: int
