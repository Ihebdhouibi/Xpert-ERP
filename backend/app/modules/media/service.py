"""Media service — upload session lifecycle and media management."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.media import storage as s3
from app.modules.media.models import MediaUploadSession, RoMedia
from app.modules.media.schemas import (
    PartUploadOut,
    RoMediaOut,
    SignedUrlResponse,
    UploadSessionOut,
)

logger = get_logger("media.service")

_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/quicktime",
}


def _storage_key(garage_id: int, filename: str) -> str:
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()[:10]
    return f"{garage_id}/media/{uuid.uuid4().hex}{ext}"


def _archive_key(original_key: str) -> str:
    return f"archive/{original_key}"


def _session_to_out(session: MediaUploadSession) -> UploadSessionOut:
    received = [p["part_number"] for p in (session.received_parts or [])]
    return UploadSessionOut(
        session_id=str(session.id),
        chunk_size_bytes=session.chunk_size_bytes,
        total_chunks=session.total_chunks,
        received_part_numbers=received,
        status=session.status,
        expires_at=session.expires_at,
    )


# ---------------------------------------------------------------------------
# Upload session
# ---------------------------------------------------------------------------

async def create_upload_session(
    db: AsyncSession,
    *,
    garage_id: int,
    inspection_id: Optional[int],
    ro_id: Optional[int],
    uploader_id: Optional[int],
    filename: str,
    mime_type: str,
    total_size_bytes: int,
    caption: Optional[str],
) -> UploadSessionOut:
    if mime_type not in _ALLOWED_MIME_TYPES:
        raise MediaMimeTypeNotAllowed(mime_type)

    cfg = get_settings()
    chunk_size = cfg.cfg_upload_chunk_size_bytes
    total_chunks = max(1, math.ceil(total_size_bytes / chunk_size))

    key = _storage_key(garage_id, filename)
    bucket = cfg.s3_bucket_media

    upload_id = await s3.create_multipart_upload(bucket, key, mime_type)

    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=cfg.cfg_media_session_ttl_hours)

    session = MediaUploadSession(
        id=uuid.uuid4(),
        garage_id=garage_id,
        inspection_id=inspection_id,
        ro_id=ro_id,
        uploader_id=uploader_id,
        filename=filename,
        mime_type=mime_type,
        total_size_bytes=total_size_bytes,
        chunk_size_bytes=chunk_size,
        total_chunks=total_chunks,
        received_parts=[],
        storage_key=key,
        s3_upload_id=upload_id,
        status="pending",
        expires_at=expires_at,
    )
    db.add(session)

    logger.info(
        "upload_session_created",
        session_id=str(session.id),
        chunks=total_chunks,
        size=total_size_bytes,
    )
    return _session_to_out(session)


async def get_upload_session(
    db: AsyncSession,
    *,
    session_id: str,
    garage_id: int,
) -> UploadSessionOut:
    session = await _get_session(db, session_id, garage_id)
    if session is None:
        raise UploadSessionNotFound(session_id)
    return _session_to_out(session)


async def receive_part(
    db: AsyncSession,
    *,
    session_id: str,
    garage_id: int,
    part_number: int,
    data: bytes,
) -> PartUploadOut:
    session = await _get_session(db, session_id, garage_id)
    if session is None:
        raise UploadSessionNotFound(session_id)
    if session.status != "pending":
        raise UploadSessionInvalidState(session.status)
    if datetime.now(tz=timezone.utc) > session.expires_at:
        raise UploadSessionExpired(session_id)
    if part_number < 1 or part_number > session.total_chunks:
        raise InvalidPartNumber(part_number, session.total_chunks)

    # Skip already-received parts (idempotent resume)
    already_received = {p["part_number"] for p in (session.received_parts or [])}
    if part_number not in already_received:
        cfg = get_settings()
        etag = await s3.upload_part(
            cfg.s3_bucket_media,
            session.storage_key,
            session.s3_upload_id,
            part_number,
            data,
        )
        new_parts = list(session.received_parts or [])
        new_parts.append({"part_number": part_number, "etag": etag})
        # SQLAlchemy won't detect mutation on a JSONB list without reassignment
        await db.execute(
            update(MediaUploadSession)
            .where(MediaUploadSession.id == session.id)
            .values(received_parts=new_parts)
        )
        session.received_parts = new_parts

    received_numbers = [p["part_number"] for p in session.received_parts]
    return PartUploadOut(part_number=part_number, received_part_numbers=received_numbers)


async def complete_upload(
    db: AsyncSession,
    *,
    session_id: str,
    garage_id: int,
    caption: Optional[str] = None,
) -> RoMediaOut:
    session = await _get_session(db, session_id, garage_id)
    if session is None:
        raise UploadSessionNotFound(session_id)
    if session.status != "pending":
        raise UploadSessionInvalidState(session.status)

    received_numbers = {p["part_number"] for p in (session.received_parts or [])}
    expected = set(range(1, session.total_chunks + 1))
    missing = expected - received_numbers
    if missing:
        raise MissingChunks(sorted(missing))

    cfg = get_settings()
    bucket = cfg.s3_bucket_media
    key = session.storage_key

    parts = sorted(session.received_parts, key=lambda p: p["part_number"])
    s3_parts = [{"PartNumber": p["part_number"], "ETag": p["etag"]} for p in parts]
    await s3.complete_multipart_upload(bucket, key, session.s3_upload_id, s3_parts)

    # Server-side EXIF stripping for images (defence-in-depth)
    size_bytes = session.total_size_bytes
    if session.mime_type.startswith("image/"):
        try:
            raw = await s3.download_object(bucket, key)
            stripped = await s3.strip_exif(raw, session.mime_type)
            if len(stripped) != len(raw):
                await s3.upload_bytes(bucket, key, stripped, session.mime_type)
                size_bytes = len(stripped)
        except Exception as exc:  # noqa: BLE001
            logger.warning("exif_strip_download_failed", session_id=session_id, error=str(exc))

    media = RoMedia(
        garage_id=garage_id,
        inspection_id=session.inspection_id,
        ro_id=session.ro_id,
        uploader_id=session.uploader_id,
        storage_key=key,
        mime_type=session.mime_type,
        size_bytes=size_bytes,
        caption=caption,
    )
    db.add(media)

    await db.execute(
        update(MediaUploadSession)
        .where(MediaUploadSession.id == session.id)
        .values(status="complete")
    )

    await db.flush()  # populate media.id / public_id

    signed_url = await s3.generate_presigned_url(bucket, key, cfg.signed_url_expiry_seconds)

    logger.info(
        "upload_completed",
        media_id=str(media.public_id),
        size=size_bytes,
        mime=session.mime_type,
    )

    return RoMediaOut(
        media_id=str(media.public_id),
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        caption=media.caption,
        uploaded_at=media.uploaded_at or datetime.now(tz=timezone.utc),
        signed_url=signed_url,
    )


# ---------------------------------------------------------------------------
# Signed URL
# ---------------------------------------------------------------------------

async def get_signed_url(
    db: AsyncSession,
    *,
    media_public_id: str,
    garage_id: int,
) -> SignedUrlResponse:
    media = await _get_media(db, media_public_id, garage_id)
    if media is None:
        raise MediaNotFound(media_public_id)

    cfg = get_settings()
    bucket = cfg.s3_bucket_media_archive if (media.archived and cfg.s3_bucket_media_archive) else cfg.s3_bucket_media
    key = media.archive_storage_key if media.archived and media.archive_storage_key else media.storage_key

    url = await s3.generate_presigned_url(bucket, key, cfg.signed_url_expiry_seconds)
    return SignedUrlResponse(
        media_id=media_public_id,
        url=url,
        expires_in_seconds=cfg.signed_url_expiry_seconds,
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def delete_media(
    db: AsyncSession,
    *,
    media_public_id: str,
    garage_id: int,
) -> None:
    media = await _get_media(db, media_public_id, garage_id)
    if media is None:
        raise MediaNotFound(media_public_id)
    media.deleted_at = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Cold-storage archiving (called by scheduler)
# ---------------------------------------------------------------------------

async def archive_old_media(db: AsyncSession) -> int:
    """Move media older than CFG_PHOTO_ARCHIVE_AFTER_DAYS to cold storage.
    Returns the number of records archived."""
    cfg = get_settings()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=cfg.cfg_photo_archive_after_days)
    archive_bucket = cfg.s3_bucket_media_archive or cfg.s3_bucket_media

    result = await db.execute(
        select(RoMedia).where(
            RoMedia.archived.is_(False),
            RoMedia.deleted_at.is_(None),
            RoMedia.uploaded_at < cutoff,
        )
    )
    rows = result.scalars().all()
    archived = 0
    for media in rows:
        try:
            src_key = media.storage_key
            dst_key = _archive_key(src_key)
            await s3.copy_object(cfg.s3_bucket_media, src_key, archive_bucket, dst_key)
            await s3.delete_object(cfg.s3_bucket_media, src_key)
            media.archived = True
            media.archive_storage_key = dst_key
            media.archived_at = datetime.now(tz=timezone.utc)
            archived += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("archive_media_failed", media_id=str(media.public_id), error=str(exc))

    if archived:
        logger.info("media_archived", count=archived)
    return archived


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_session(
    db: AsyncSession, session_id: str, garage_id: int
) -> Optional[MediaUploadSession]:
    try:
        uid = uuid.UUID(session_id)
    except ValueError:
        return None
    result = await db.execute(
        select(MediaUploadSession).where(
            MediaUploadSession.id == uid,
            MediaUploadSession.garage_id == garage_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_media(
    db: AsyncSession, public_id_str: str, garage_id: int
) -> Optional[RoMedia]:
    try:
        uid = uuid.UUID(public_id_str)
    except ValueError:
        return None
    result = await db.execute(
        select(RoMedia).where(
            RoMedia.public_id == uid,
            RoMedia.garage_id == garage_id,
            RoMedia.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class MediaMimeTypeNotAllowed(ValueError):
    def __init__(self, mime: str) -> None:
        super().__init__(f"MIME type '{mime}' is not allowed for media upload")


class UploadSessionNotFound(LookupError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Upload session '{session_id}' not found")


class UploadSessionInvalidState(ValueError):
    def __init__(self, status: str) -> None:
        super().__init__(f"Upload session is in state '{status}' and cannot accept new data")


class UploadSessionExpired(ValueError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Upload session '{session_id}' has expired")


class InvalidPartNumber(ValueError):
    def __init__(self, part_number: int, total_chunks: int) -> None:
        super().__init__(f"Part number {part_number} is outside the valid range [1, {total_chunks}]")


class MissingChunks(ValueError):
    def __init__(self, missing: list[int]) -> None:
        super().__init__(f"Cannot complete upload — missing chunks: {missing}")
        self.missing = missing


class MediaNotFound(LookupError):
    def __init__(self, media_id: str) -> None:
        super().__init__(f"Media '{media_id}' not found")
