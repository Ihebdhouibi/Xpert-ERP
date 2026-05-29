"""Accounting export API router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.accounting_export import service
from app.modules.accounting_export.schemas import (
    AccountingExportCreateRequest,
    AccountingExportListResponse,
    AccountingExportOut,
    AccountingExportPreviewResponse,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/accounting-exports", tags=["accounting-exports"])


@router.get(
    "/preview",
    response_model=AccountingExportPreviewResponse,
    dependencies=[require_permission("accounting_export.read")],
)
async def preview_export(
    user: AuthUser,
    period_start: str = Query(..., description="ISO date YYYY-MM-DD"),
    period_end: str = Query(..., description="ISO date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Return counts of pending vs already-exported records in the period."""
    counts = await service.preview_export(
        db, user.garage_id, period_start, period_end
    )
    already = (
        counts["already_exported_invoices"]
        + counts["already_exported_payments"]
        + counts["already_exported_supplier_invoices"]
    )
    warning = (
        f"{already} record(s) in this period have already been exported. "
        "Only unexported records will be included in a new export."
        if already > 0
        else None
    )
    return AccountingExportPreviewResponse(**counts, warning=warning)


@router.post(
    "",
    response_model=AccountingExportOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("accounting_export.create")],
)
async def create_export(
    user: AuthUser,
    body: AccountingExportCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an accounting export for the given period."""
    try:
        export = await service.create_export(
            db,
            garage_id=user.garage_id,
            period_start=body.period_start.isoformat(),
            period_end=body.period_end.isoformat(),
            fmt=body.format,
            user_id=user.user_id,
        )
    except service.AccountingExportInvalidFormatError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {exc}",
        )
    return AccountingExportOut.model_validate(export)


@router.get(
    "",
    response_model=AccountingExportListResponse,
    dependencies=[require_permission("accounting_export.read")],
)
async def list_exports(
    user: AuthUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_exports(db, user.garage_id, page, page_size)
    return AccountingExportListResponse(
        items=[AccountingExportOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{public_id}",
    response_model=AccountingExportOut,
    dependencies=[require_permission("accounting_export.read")],
)
async def get_export(
    user: AuthUser,
    public_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        export = await service.get_export(db, user.garage_id, public_id)
    except service.AccountingExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return AccountingExportOut.model_validate(export)


@router.get(
    "/{public_id}/download",
    dependencies=[require_permission("accounting_export.download")],
)
async def download_export(
    user: AuthUser,
    public_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a pre-signed URL to download the export ZIP."""
    try:
        url = await service.get_download_url(db, user.garage_id, public_id)
    except service.AccountingExportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found or file not available",
        )
    return {"download_url": url}
