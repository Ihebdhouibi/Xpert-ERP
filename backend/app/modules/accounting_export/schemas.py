"""Pydantic schemas for accounting export."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AccountingExportCreateRequest(BaseModel):
    period_start: date
    period_end: date
    format: Optional[str] = None  # overrides CFG_ACCOUNTING_FORMAT when set


class AccountingExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    garage_id: int
    period_start: str
    period_end: str
    format: str
    status: str
    file_storage_key: Optional[str] = None
    exported_by: Optional[int] = None
    exported_at: Optional[datetime] = None
    record_counts: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AccountingExportListResponse(BaseModel):
    items: list[AccountingExportOut]
    total: int
    page: int
    page_size: int


class AccountingExportPreviewResponse(BaseModel):
    """Returned before export is committed when re-export risk detected."""
    already_exported_invoices: int
    already_exported_payments: int
    already_exported_supplier_invoices: int
    pending_invoices: int
    pending_payments: int
    pending_supplier_invoices: int
    warning: Optional[str] = None
