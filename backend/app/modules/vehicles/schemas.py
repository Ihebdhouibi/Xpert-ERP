"""Pydantic schemas for the Vehicle module."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.vehicles.models import FuelType, VehicleStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class VehicleCreateRequest(BaseModel):
    customer_id: Optional[int] = None
    registration: Optional[str] = Field(None, max_length=50)
    vin: Optional[str] = Field(None, min_length=11, max_length=17)
    make: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    fuel_type: Optional[FuelType] = None
    color: Optional[str] = Field(None, max_length=50)
    mileage_current: Optional[int] = Field(None, ge=0)
    technical_inspection_due_at: Optional[datetime] = None
    maintenance_due_at: Optional[datetime] = None

    @model_validator(mode="after")
    def require_registration_or_vin(self) -> "VehicleCreateRequest":
        if not self.registration and not self.vin:
            raise ValueError("At least one of 'registration' or 'vin' must be provided")
        return self


class VehicleUpdateRequest(BaseModel):
    customer_id: Optional[int] = None
    make: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    fuel_type: Optional[FuelType] = None
    color: Optional[str] = Field(None, max_length=50)
    mileage_current: Optional[int] = Field(None, ge=0)
    last_service_at: Optional[datetime] = None
    technical_inspection_due_at: Optional[datetime] = None
    maintenance_due_at: Optional[datetime] = None
    status: Optional[VehicleStatus] = None


class OwnershipTransferRequest(BaseModel):
    new_customer_id: Optional[int] = Field(
        None, description="New owner's customer ID. NULL releases the vehicle from any owner."
    )
    note: Optional[str] = Field(None, max_length=500)


class ReRegistrationRequest(BaseModel):
    new_registration: str = Field(..., min_length=1, max_length=50)
    note: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class OwnershipHistoryOut(BaseModel):
    id: int
    vehicle_id: int
    previous_customer_id: Optional[int]
    new_customer_id: Optional[int]
    transferred_by: Optional[int]
    note: Optional[str]
    transferred_at: datetime

    model_config = {"from_attributes": True}


class RegistrationAliasOut(BaseModel):
    id: int
    registration: str
    valid_until: Optional[datetime]
    note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class VehicleOut(BaseModel):
    id: int
    garage_id: int
    customer_id: Optional[int]
    registration: Optional[str]
    vin: Optional[str]
    make: str
    model: str
    year: Optional[int]
    fuel_type: Optional[FuelType]
    color: Optional[str]
    mileage_current: Optional[int]
    last_service_at: Optional[datetime]
    technical_inspection_due_at: Optional[datetime]
    maintenance_due_at: Optional[datetime]
    status: VehicleStatus
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VehicleListResponse(BaseModel):
    items: list[VehicleOut]
    total: int
    page: int
    page_size: int


class VehicleROSummary(BaseModel):
    """Minimal repair-order summary embedded in the vehicle history response."""
    id: int
    public_id: str
    status: str
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if hasattr(data, "public_id"):
            data.__dict__["public_id"] = str(data.public_id)
        return data


class VehicleHistoryOut(BaseModel):
    vehicle: VehicleOut
    ownership_history: list[OwnershipHistoryOut]
    registration_aliases: list[RegistrationAliasOut]
    repair_orders: list[VehicleROSummary] = Field(default_factory=list)
