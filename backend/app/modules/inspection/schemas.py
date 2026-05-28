from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── Template schemas ──────────────────────────────────────────────────────────

class TemplateItemSchema(BaseModel):
    id: str
    label: str
    requires_photo: bool = False


class TemplateSectionSchema(BaseModel):
    id: str
    title: str
    items: List[TemplateItemSchema] = []


class InspectionTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sections: List[TemplateSectionSchema] = []


class InspectionTemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sections: Optional[List[TemplateSectionSchema]] = None
    version: int


class InspectionTemplateSummary(BaseModel):
    id: str
    name: str
    sections: Any
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, obj: Any) -> "InspectionTemplateSummary":
        return cls(
            id=str(obj.public_id),
            name=obj.name,
            sections=obj.sections,
            version=obj.version,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class InspectionTemplateListResponse(BaseModel):
    items: List[InspectionTemplateSummary]
    total: int
    page: int
    page_size: int


# ── Inspection schemas ────────────────────────────────────────────────────────

class InspectionCreateRequest(BaseModel):
    template_public_id: str
    mechanic_id: Optional[int] = None
    repair_order_public_id: Optional[str] = None
    vehicle_id: Optional[int] = None


class InspectionStatusTransitionRequest(BaseModel):
    new_status: str


class ItemResultPayload(BaseModel):
    item_id: str
    status: str
    notes: Optional[str] = None
    media_ids: List[str] = []
    written_at: Optional[datetime] = None


class BulkResultsRequest(BaseModel):
    items: List[ItemResultPayload]


class ItemResultResponse(BaseModel):
    item_id: str
    status: str
    notes: Optional[str]
    media_ids: List[str]
    written_at: datetime

    @classmethod
    def from_orm(cls, obj: Any) -> "ItemResultResponse":
        return cls(
            item_id=obj.item_id,
            status=obj.status.value,
            notes=obj.notes,
            media_ids=obj.media_ids or [],
            written_at=obj.written_at,
        )


class ConflictLogEntry(BaseModel):
    item_id: str
    client_written_at: datetime
    server_written_at: datetime
    discarded_status: str
    kept_status: str


class BulkResultsResponse(BaseModel):
    synced: int
    conflicts: List[ConflictLogEntry]


class InspectionSummary(BaseModel):
    id: str
    template_id: str
    template_name: str
    mechanic_id: Optional[int]
    repair_order_id: Optional[str]
    vehicle_id: Optional[int]
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class InspectionDetail(BaseModel):
    id: str
    template_id: str
    template_name: str
    template_sections: Any
    mechanic_id: Optional[int]
    repair_order_id: Optional[str]
    vehicle_id: Optional[int]
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    results: List[ItemResultResponse]
    version: int


class InspectionListResponse(BaseModel):
    items: List[InspectionSummary]
    total: int
    page: int
    page_size: int


class DeclinedItemPayload(BaseModel):
    item_id: str
    item_label: str
    item_status: str
    notes: Optional[str] = None


class ArchiveDeclinedRequest(BaseModel):
    vehicle_id: int
    declined_items: List[DeclinedItemPayload]


class VehicleRecommendationResponse(BaseModel):
    id: str
    vehicle_id: int
    item_id: str
    item_label: str
    item_status: str
    status: str
    notes: Optional[str]
    created_at: datetime

    @classmethod
    def from_orm(cls, obj: Any) -> "VehicleRecommendationResponse":
        return cls(
            id=str(obj.public_id),
            vehicle_id=obj.vehicle_id,
            item_id=obj.item_id,
            item_label=obj.item_label,
            item_status=obj.item_status,
            status=obj.status,
            notes=obj.notes,
            created_at=obj.created_at,
        )


class ConvertToRORequest(BaseModel):
    repair_order_public_id: str


# ── Approval link schemas ──────────────────────────────────────────────────────

class GenerateApprovalLinkResponse(BaseModel):
    token: str
    expires_at: datetime


class ApprovalPublicItem(BaseModel):
    item_id: str
    item_label: str
    item_status: Optional[str]  # None if not yet evaluated
    notes: Optional[str]
    actionable: bool  # True when status is attention or defective


class ApprovalPublicSection(BaseModel):
    section_id: str
    section_title: str
    items: List[ApprovalPublicItem]


class ApprovalPublicInspection(BaseModel):
    inspection_id: str
    template_name: str
    vehicle_info: str
    mechanic_name: str
    completed_at: Optional[datetime]
    sections: List[ApprovalPublicSection]


class ApprovalItemDecision(BaseModel):
    item_id: str
    decision: str  # "approved" | "rejected"


class ProcessApprovalRequest(BaseModel):
    decisions: List[ApprovalItemDecision]


class ProcessApprovalResponse(BaseModel):
    repair_tasks_created: int
    recommendations_archived: int
