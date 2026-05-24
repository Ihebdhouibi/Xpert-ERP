from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TimeEntryStartRequest(BaseModel):
    notes: Optional[str] = None


class TimeEntryStopRequest(BaseModel):
    notes: Optional[str] = None


class TimeEntrySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ro_id: int
    user_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    duration_minutes: Optional[int]
    notes: Optional[str]

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


class TimeEntryListResponse(BaseModel):
    items: list[TimeEntrySummary]
    total: int


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class CommentCreateRequest(BaseModel):
    body: str = Field(..., min_length=1)


class CommentUpdateRequest(BaseModel):
    body: str = Field(..., min_length=1)


class CommentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ro_id: int
    user_id: Optional[int]
    body: str
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    items: list[CommentSummary]
    total: int
