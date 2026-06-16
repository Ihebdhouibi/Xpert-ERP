"""Pydantic schemas for the Bon de Retour module."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.modules.bon_de_retour.models import (
    BonDeRetourLineCondition,
    BonDeRetourPartyType,
    BonDeRetourStatus,
    SupplierCreditNoteStatus,
)


# ---------------------------------------------------------------------------
# Line schemas
# ---------------------------------------------------------------------------

class BonDeRetourLineCreateRequest(BaseModel):
    part_id: Optional[int] = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price_minor: int = Field(default=0, ge=0)
    vat_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)
    condition: Optional[BonDeRetourLineCondition] = None
    restock: bool = True


class BonDeRetourLineUpdateRequest(BaseModel):
    part_id: Optional[int] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[Decimal] = Field(None, gt=0, decimal_places=3)
    unit_price_minor: Optional[int] = Field(None, ge=0)
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    condition: Optional[BonDeRetourLineCondition] = None
    restock: Optional[bool] = None


class BonDeRetourLineOut(BaseModel):
    id: int
    bon_de_retour_id: int
    part_id: Optional[int]
    description: str
    quantity: Decimal
    unit_price_minor: int
    vat_rate: Decimal
    line_total_minor: int
    condition: Optional[BonDeRetourLineCondition]
    restock: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Header schemas
# ---------------------------------------------------------------------------

class BonDeRetourCreateRequest(BaseModel):
    party_type: BonDeRetourPartyType
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    source_invoice_id: Optional[int] = None
    source_supplier_invoice_id: Optional[int] = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    reason: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    lines: list[BonDeRetourLineCreateRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_party(self) -> "BonDeRetourCreateRequest":
        if self.party_type == BonDeRetourPartyType.client:
            if self.customer_id is None:
                raise ValueError("customer_id is required for a client return")
            self.supplier_id = None
        else:
            if self.supplier_id is None:
                raise ValueError("supplier_id is required for a supplier return")
            self.customer_id = None
        return self


class BonDeRetourUpdateRequest(BaseModel):
    source_invoice_id: Optional[int] = None
    source_supplier_invoice_id: Optional[int] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    reason: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)


class BonDeRetourOut(BaseModel):
    id: int
    public_id: str
    garage_id: int
    party_type: BonDeRetourPartyType
    customer_id: Optional[int]
    supplier_id: Optional[int]
    source_invoice_id: Optional[int]
    source_supplier_invoice_id: Optional[int]
    doc_number: Optional[str]
    status: BonDeRetourStatus
    reason: Optional[str]
    notes: Optional[str]
    subtotal_minor: int
    vat_minor: int
    total_minor: int
    currency: str
    credit_note_id: Optional[int]
    supplier_credit_note_id: Optional[int]
    version: int
    confirmed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    reversed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    lines: list[BonDeRetourLineOut] = []

    # Denormalised display fields (populated by the service layer)
    customer_name: Optional[str] = None
    supplier_name: Optional[str] = None
    credit_note_doc_number: Optional[str] = None
    supplier_credit_note_doc_number: Optional[str] = None

    model_config = {"from_attributes": True}


class BonDeRetourListResponse(BaseModel):
    items: list[BonDeRetourOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Avoir creation requests
# ---------------------------------------------------------------------------

class CreateCreditNoteRequest(BaseModel):
    """Client side — create an avoir (existing credit_note module)."""
    invoice_id: Optional[int] = None          # falls back to the BR's source_invoice_id
    total_minor: Optional[int] = Field(None, ge=0)  # falls back to the BR total
    reason: Optional[str] = Field(None, max_length=2000)


class CreateSupplierCreditNoteRequest(BaseModel):
    """Supplier side — create the minimal avoir fournisseur."""
    total_ht_minor: Optional[int] = Field(None, ge=0)   # falls back to the BR subtotal
    total_ttc_minor: Optional[int] = Field(None, ge=0)  # falls back to the BR total
    reason: Optional[str] = Field(None, max_length=2000)


class SupplierCreditNoteOut(BaseModel):
    id: int
    public_id: str
    garage_id: int
    supplier_id: int
    supplier_invoice_id: Optional[int]
    bon_de_retour_id: Optional[int]
    doc_number: Optional[str]
    status: SupplierCreditNoteStatus
    total_ht_minor: int
    total_ttc_minor: int
    reason: Optional[str]
    issued_at: Optional[datetime]
    voided_at: Optional[datetime]
    is_exported: bool = False
    created_at: datetime
    updated_at: datetime

    # Denormalised display fields (populated by the service layer)
    supplier_name: Optional[str] = None
    bon_de_retour_public_id: Optional[str] = None

    model_config = {"from_attributes": True}


class SupplierCreditNoteListResponse(BaseModel):
    items: list[SupplierCreditNoteOut]
    total: int
    page: int
    page_size: int
