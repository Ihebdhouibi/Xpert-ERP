from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.repair_order.models import ROStatus


class ROLaborLineCreateRequest(BaseModel):
    """Request to add a labor line to a repair order."""
    labor_type: str = Field(..., min_length=1, max_length=100)
    duration_minutes: int = Field(..., gt=0)
    rate_minor: int = Field(..., gt=0)


class ROPartLineCreateRequest(BaseModel):
    """Request to add a part line to a repair order."""
    part_name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., gt=0)
    unit_cost_minor: int = Field(..., gt=0)


class RepairOrderCreateRequest(BaseModel):
    """Request to create a repair order."""
    customer_id: int = Field(..., gt=0)
    vehicle_id: Optional[int] = Field(None, gt=0)
    description: str = Field(..., min_length=1)
    priority: Optional[str] = Field(None, max_length=20)
    estimated_cost_minor: Optional[int] = Field(None, ge=0)
    estimated_cost_currency: Optional[str] = Field(None, min_length=3, max_length=3)

    @field_validator("estimated_cost_currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.isupper() or len(v) != 3:
                raise ValueError("Currency must be 3 uppercase letters (ISO 4217)")
        return v


class RepairOrderUpdateRequest(BaseModel):
    """Request to update a repair order."""
    description: Optional[str] = Field(None, min_length=1)
    priority: Optional[str] = Field(None, max_length=20)
    estimated_cost_minor: Optional[int] = Field(None, ge=0)
    estimated_cost_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    notes: Optional[str] = None

    @field_validator("estimated_cost_currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.isupper() or len(v) != 3:
                raise ValueError("Currency must be 3 uppercase letters (ISO 4217)")
        return v


class StatusTransitionRequest(BaseModel):
    """Request to transition repair order to a new status."""
    new_status: ROStatus
    reason: Optional[str] = None


class ROLaborLineSummary(BaseModel):
    """Labor line summary in list/detail views."""
    id: int
    labor_type: str
    duration_minutes: int
    rate_minor: int
    amount_minor: int
    created_at: datetime

    class Config:
        from_attributes = True


class ROPartLineSummary(BaseModel):
    """Part line summary in list/detail views."""
    id: int
    part_name: str
    quantity: int
    unit_cost_minor: int
    amount_minor: int
    created_at: datetime

    class Config:
        from_attributes = True


class ROStatusEventSummary(BaseModel):
    """Status event entry in history."""
    id: int
    old_status: Optional[str]
    new_status: str
    occurred_at: datetime

    class Config:
        from_attributes = True


class RepairOrderSummary(BaseModel):
    """Repair order summary for list view."""
    id: str  # public_id
    customer_id: int
    vehicle_id: Optional[int]
    description: str
    status: ROStatus
    priority: Optional[str]
    estimated_cost_minor: Optional[int]
    estimated_cost_currency: Optional[str]
    actual_cost_minor: int
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True

    @field_validator("id", mode="before")
    @classmethod
    def convert_public_id(cls, v):
        """Convert UUID to string."""
        return str(v) if v else v


class RepairOrderDetail(BaseModel):
    """Repair order full detail with line items and status history."""
    id: str  # public_id
    customer_id: int
    vehicle_id: Optional[int]
    description: str
    status: ROStatus
    priority: Optional[str]
    estimated_cost_minor: Optional[int]
    estimated_cost_currency: Optional[str]
    actual_cost_minor: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    version: int

    labor_lines: list[ROLaborLineSummary] = []
    part_lines: list[ROPartLineSummary] = []
    status_events: list[ROStatusEventSummary] = []

    class Config:
        from_attributes = True
        populate_by_name = True

    @field_validator("id", mode="before")
    @classmethod
    def convert_public_id(cls, v):
        """Convert UUID to string."""
        return str(v) if v else v
