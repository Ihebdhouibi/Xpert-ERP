from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GarageSettingOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    garage_id: int
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime
    updated_by: Optional[int]


class GarageSettingUpsertRequest(BaseModel):
    value: str = Field(..., min_length=1, max_length=4096)
    description: Optional[str] = Field(None, max_length=1024)


class GarageSettingListResponse(BaseModel):
    items: list[GarageSettingOut]
    total: int
