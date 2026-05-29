"""Media router — chunked upload sessions, signed URLs, delete."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.inspection.models import Inspection
from app.modules.media import service
from app.modules.media.schemas import (
    PartUploadOut,
    RoMediaOut,
    SignedUrlResponse,
    UploadSessionCreate,
    UploadSessionOut,
)
from app.modules.media.service import (
    InvalidPartNumber,
    MediaMimeTypeNotAllowed,
    MediaNotFound,
    MissingChunks,
    UploadSessionExpired,
    UploadSessionInvalidState,
    UploadSessionNotFound,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/media", tags=["media"])


async def _resolve_inspection(
    db: AsyncSession, garage_id: int, public_id: str
) -> Optional[Inspection]:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(public_id)
    except ValueError:
        return None
    result = await db.execute(
        select(Inspection).where(
            Inspection.public_id == uid,
            Inspection.garage_id == garage_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Upload session lifecycle
# ---------------------------------------------------------------------------

@router.post(
    "/upload-sessions",
    response_model=UploadSessionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("inspection.write")],
    summary="Initiate a resumable chunked upload session",
)
async def create_session(
    body: UploadSessionCreate,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> UploadSessionOut:
    inspection = await _resolve_inspection(db, user.garage_id, body.inspection_public_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found")

    try:
        out = await service.create_upload_session(
            db,
            garage_id=user.garage_id,
            inspection_id=inspection.id,
            ro_id=inspection.repair_order_id,
            uploader_id=None,  # resolved below if needed
            filename=body.filename,
            mime_type=body.mime_type,
            total_size_bytes=body.total_size_bytes,
            caption=body.caption,
        )
    except MediaMimeTypeNotAllowed as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    await db.commit()
    return out


@router.get(
    "/upload-sessions/{session_id}",
    response_model=UploadSessionOut,
    dependencies=[require_permission("inspection.write")],
    summary="Get upload session state (for resume)",
)
async def get_session(
    session_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> UploadSessionOut:
    try:
        return await service.get_upload_session(db, session_id=session_id, garage_id=user.garage_id)
    except UploadSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/upload-sessions/{session_id}/parts/{part_number}",
    response_model=PartUploadOut,
    dependencies=[require_permission("inspection.write")],
    summary="Upload one chunk (1-based part number)",
)
async def upload_part(
    session_id: str,
    part_number: int,
    request: Request,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> PartUploadOut:
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty chunk body")

    try:
        result = await service.receive_part(
            db,
            session_id=session_id,
            garage_id=user.garage_id,
            part_number=part_number,
            data=data,
        )
    except UploadSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (UploadSessionInvalidState, UploadSessionExpired, InvalidPartNumber) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc

    await db.commit()
    return result


@router.post(
    "/upload-sessions/{session_id}/complete",
    response_model=RoMediaOut,
    dependencies=[require_permission("inspection.write")],
    summary="Finalise the upload and create the media record",
)
async def complete_session(
    session_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    caption: Optional[str] = Query(None, max_length=500),
) -> RoMediaOut:
    try:
        out = await service.complete_upload(
            db,
            session_id=session_id,
            garage_id=user.garage_id,
            caption=caption,
        )
    except UploadSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UploadSessionInvalidState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MissingChunks as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc

    await db.commit()
    return out


# ---------------------------------------------------------------------------
# Signed URL + delete
# ---------------------------------------------------------------------------

@router.get(
    "/{media_id}/signed-url",
    response_model=SignedUrlResponse,
    dependencies=[require_permission("inspection.read")],
    summary="Get a short-lived pre-signed download URL",
)
async def get_signed_url(
    media_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SignedUrlResponse:
    try:
        return await service.get_signed_url(db, media_public_id=media_id, garage_id=user.garage_id)
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("inspection.write")],
    summary="Soft-delete a media record",
)
async def delete_media(
    media_id: str,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.delete_media(db, media_public_id=media_id, garage_id=user.garage_id)
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
