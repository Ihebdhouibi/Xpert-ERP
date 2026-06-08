from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    part_public_id: Optional[str] = Field(
        None, description="Catalog part public_id (UUID) — enables stock reservation"
    )


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
    part_id: Optional[int] = None
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


class AssignMechanicRequest(BaseModel):
    """Request to assign (or unassign) a mechanic to a repair order."""
    user_id: Optional[int] = Field(None, gt=0)


class RepairOrderSummary(BaseModel):
    """Repair order summary for list view."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str  # public_id
    customer_id: int
    customer_name: Optional[str] = None
    vehicle_id: Optional[int]
    description: str
    status: ROStatus
    priority: Optional[str]
    estimated_cost_minor: Optional[int]
    estimated_cost_currency: Optional[str]
    actual_cost_minor: int
    assigned_user_id: Optional[int]
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _remap_public_id(cls, data):
        """When validating from ORM object, use public_id as id."""
        if hasattr(data, "public_id"):
            return {
                "id": str(data.public_id),
                "customer_id": data.customer_id,
                "vehicle_id": data.vehicle_id,
                "description": data.description,
                "status": data.status,
                "priority": data.priority,
                "estimated_cost_minor": data.estimated_cost_minor,
                "estimated_cost_currency": data.estimated_cost_currency,
                "actual_cost_minor": data.actual_cost_minor,
                "assigned_user_id": data.assigned_user_id,
                "created_at": data.created_at,
            }
        return data


class MechanicSummary(BaseModel):
    """An assignable mechanic with their current workload."""
    id: int
    name: str
    active_orders: int  # repair orders currently assigned & not finished/delivered


class RepairOrderDetail(BaseModel):
    """Repair order full detail with line items and status history."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str  # public_id
    customer_id: int
    customer_name: Optional[str] = None
    vehicle_id: Optional[int]
    description: str
    status: ROStatus
    priority: Optional[str]
    estimated_cost_minor: Optional[int]
    estimated_cost_currency: Optional[str]
    actual_cost_minor: int
    assigned_user_id: Optional[int]
    assigned_user_name: Optional[str] = None
    assignment_accepted_at: Optional[datetime] = None
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    version: int

    labor_lines: list[ROLaborLineSummary] = []
    part_lines: list[ROPartLineSummary] = []
    status_events: list[ROStatusEventSummary] = []

    @model_validator(mode="before")
    @classmethod
    def _remap_public_id(cls, data):
        """When validating from ORM object, use public_id as id."""
        if hasattr(data, "public_id"):
            return {
                "id": str(data.public_id),
                "customer_id": data.customer_id,
                "vehicle_id": data.vehicle_id,
                "description": data.description,
                "status": data.status,
                "priority": data.priority,
                "estimated_cost_minor": data.estimated_cost_minor,
                "estimated_cost_currency": data.estimated_cost_currency,
                "actual_cost_minor": data.actual_cost_minor,
                "assigned_user_id": data.assigned_user_id,
                "assignment_accepted_at": data.assignment_accepted_at,
                "notes": data.notes,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "version": data.version,
                "labor_lines": data.labor_lines,
                "part_lines": data.part_lines,
                "status_events": data.status_events,
            }
        return data


class ROPhotoSummary(BaseModel):
    """Photo summary with a presigned download URL."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    ro_id: int
    uploaded_by_user_id: Optional[int]
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    url: str = ""  # populated by the router after presigned URL generation


class ROPhotoListResponse(BaseModel):
    items: list[ROPhotoSummary]
    total: int
