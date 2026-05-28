"""Pydantic request / response schemas for the media module."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Upload session
# ---------------------------------------------------------------------------

class UploadSessionCreate(BaseModel):
    inspection_public_id: str
    filename: str = Field(..., max_length=512)
    mime_type: str = Field(..., max_length=127)
    total_size_bytes: int = Field(..., gt=0)
    caption: Optional[str] = None


class UploadSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    chunk_size_bytes: int
    total_chunks: int
    # part numbers (1-based) already received — client skips these on resume
    received_part_numbers: list[int]
    status: str
    expires_at: datetime


class PartUploadOut(BaseModel):
    part_number: int
    received_part_numbers: list[int]


# ---------------------------------------------------------------------------
# Completed media record
# ---------------------------------------------------------------------------

class RoMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    media_id: str
    mime_type: str
    size_bytes: int
    caption: Optional[str]
    uploaded_at: datetime
    signed_url: str


class SignedUrlResponse(BaseModel):
    media_id: str
    url: str
    expires_in_seconds: int
