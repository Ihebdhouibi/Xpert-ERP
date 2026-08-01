from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.modules.parts.models import PartStatus


# ---------------------------------------------------------------------------
# Part Category
# ---------------------------------------------------------------------------

class PartCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = Field(None, gt=0)


class PartCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = Field(None, gt=0)


class PartCategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    garage_id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    part_count: int = 0


class PartCategoryTree(PartCategorySummary):
    children: list[PartCategoryTree] = []


# ---------------------------------------------------------------------------
# Part
# ---------------------------------------------------------------------------

class PartCreate(BaseModel):
    sku_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[int] = Field(None, gt=0)
    unit_of_measure: str = Field("pcs", max_length=20)
    purchase_price_minor: StrictInt = Field(..., ge=0)
    selling_price_minor: StrictInt = Field(..., ge=0)
    supplier_hint_id: Optional[int] = Field(None, gt=0)
    reorder_threshold: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=1)
    status: PartStatus = PartStatus.active

    @field_validator("sku_code")
    @classmethod
    def sku_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class PartUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[int] = Field(None, gt=0)
    unit_of_measure: Optional[str] = Field(None, max_length=20)
    purchase_price_minor: Optional[StrictInt] = Field(None, ge=0)
    selling_price_minor: Optional[StrictInt] = Field(None, ge=0)
    supplier_hint_id: Optional[int] = Field(None, gt=0)
    reorder_threshold: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=1)
    status: Optional[PartStatus] = None


class PartSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    int_id: int
    sku_code: str
    name: str
    description: Optional[str]
    category_id: Optional[int]
    unit_of_measure: str
    purchase_price_minor: int
    selling_price_minor: int
    supplier_hint_id: Optional[int]
    reorder_threshold: Optional[int]
    reorder_quantity: Optional[int]
    status: PartStatus
    stock_on_hand: int = 0
    version: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _remap_public_id(cls, data: Any) -> Any:
        if hasattr(data, "public_id") and not isinstance(data, dict):
            values = dict(data.__dict__)
            values["int_id"] = values["id"]
            values["id"] = str(data.public_id)
            return values
        return data


class PartDetail(PartSummary):
    garage_id: int
    deleted_at: Optional[datetime]
    category: Optional[PartCategorySummary]
    equivalents: list[PartSummary] = []


class PartListResponse(BaseModel):
    items: list[PartSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Equivalents
# ---------------------------------------------------------------------------

class EquivalentLinkRequest(BaseModel):
    target_id: str = Field(..., description="public_id of the target part")
