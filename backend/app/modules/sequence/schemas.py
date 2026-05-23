"""Pydantic schemas for the document sequence module."""
from __future__ import annotations

from pydantic import BaseModel, Field


DOC_TYPES = {"QUOT", "INV", "CRNOTE", "DO"}


class SequenceStateOut(BaseModel):
    """Read-only view of the current sequence counter — for admin inspection."""
    garage_id: int
    doc_type: str
    year: int
    last_number: int

    model_config = {"from_attributes": True}


class NextNumberOut(BaseModel):
    """Returned by the internal service; not exposed directly as an HTTP response."""
    doc_type: str
    year: int
    number: int
    formatted: str  # e.g. "INV-2026-00001"
