"""Document service — validation, upload orchestration, signed-URL generation, archiver."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.documents import repository as repo
from app.modules.documents import storage
from app.modules.documents.models import Document, DocumentCategory, OwnerEntityType
from app.modules.documents.schemas import DocumentListResponse, DocumentOut, SignedUrlResponse

logger = get_logger("documents.service")

# ---------------------------------------------------------------------------
# Magic-byte signatures for server-side MIME verification
# ---------------------------------------------------------------------------
_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


def _detect_mime_from_header(header: bytes) -> Optional[str]:
    """Return detected MIME type from the first 12 bytes, or None."""
    for magic, mime in _MAGIC:
        if header[: len(magic)] == magic:
            return mime
    # WebP: "RIFF????WEBP"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _build_storage_key(garage_id: int, category: str, original_name: str) -> str:
    """Build a non-guessable S3 object key scoped to garage + category."""
    ext = ""
    if "." in original_name:
        ext = "." + original_name.rsplit(".", 1)[-1].lower()[:10]
    return f"{garage_id}/{category}/{uuid.uuid4().hex}{ext}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def upload_document(
    db: AsyncSession,
    *,
    file: UploadFile,
    category: DocumentCategory,
    owner_entity_type: OwnerEntityType,
    owner_entity_id: Optional[int],
    garage_id: int,
    uploaded_by: int,
    background_tasks: Optional[BackgroundTasks] = None,
) -> DocumentOut:
    cfg = get_settings()

    # 1. Read file content (bounded by max size + 1 to detect oversize)
    raw = await file.read(cfg.max_upload_size_bytes + 1)
    if len(raw) > cfg.max_upload_size_bytes:
        raise FileTooLargeError(cfg.max_upload_size_bytes)

    if len(raw) == 0:
        raise ValueError("Uploaded file is empty")

    # 2. Server-side MIME verification via magic bytes
    detected = _detect_mime_from_header(raw[:12])
    declared = (file.content_type or "").split(";")[0].strip().lower()

    # Use detected type when available; fall back to declared
    effective_mime = detected or declared

    if effective_mime not in cfg.allowed_mime_types:
        raise MimeTypeNotAllowedError(effective_mime, cfg.allowed_mime_types)

    # If declared and detected disagree, reject (possible spoofing)
    if detected and declared and detected != declared:
        raise MimeTypeNotAllowedError(
            declared,
            cfg.allowed_mime_types,
            detail="Declared MIME type does not match file content",
        )

    # 3. SHA-256 integrity hash
    sha256 = hashlib.sha256(raw).hexdigest()

    # 4. Build storage key and upload
    filename = file.filename or "upload"
    key = _build_storage_key(garage_id, category.value, filename)

    await storage.upload_bytes(
        bucket=cfg.s3_bucket_documents,
        key=key,
        data=raw,
        content_type=effective_mime,
    )
    logger.info("document_uploaded", key=key, size=len(raw), garage_id=garage_id)

    # 5. Persist metadata
    doc = await repo.create_document(
        db,
        garage_id=garage_id,
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        category=category,
        filename=filename,
        mime_type=effective_mime,
        size_bytes=len(raw),
        sha256=sha256,
        storage_key=key,
        uploaded_by=uploaded_by,
    )

    # 6. Enqueue OCR for documents that benefit from structured extraction
    if background_tasks is not None and category in (
        DocumentCategory.registration_card,
        DocumentCategory.id_doc,
    ):
        from app.modules.ocr.service import enqueue_ocr, process_ocr_job

        async def _ocr_pipeline() -> None:
            extraction = await enqueue_ocr(db, document_id=doc.id)
            await process_ocr_job(db, extraction_id=extraction.id)

        background_tasks.add_task(_ocr_pipeline)

    return DocumentOut.from_model(doc)


async def get_signed_url(
    db: AsyncSession,
    *,
    document_public_id: uuid.UUID,
    garage_id: int,
) -> SignedUrlResponse:
    cfg = get_settings()

    doc: Document | None = await repo.get_by_public_id(
        db, public_id=document_public_id, garage_id=garage_id
    )
    if doc is None:
        raise DocumentNotFoundError(document_public_id)

    url = await storage.generate_presigned_url(
        bucket=cfg.s3_bucket_documents,
        key=doc.storage_key,
        expiry_seconds=cfg.signed_url_expiry_seconds,
    )

    return SignedUrlResponse(
        document_id=str(doc.public_id),
        url=url,
        expires_in_seconds=cfg.signed_url_expiry_seconds,
    )


async def list_documents(
    db: AsyncSession,
    *,
    garage_id: int,
    category: Optional[DocumentCategory] = None,
    owner_entity_type: Optional[OwnerEntityType] = None,
    owner_entity_id: Optional[int] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> DocumentListResponse:
    docs = await repo.list_documents(
        db,
        garage_id=garage_id,
        category=category,
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        from_date=from_date,
        to_date=to_date,
        q=q,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        items=[DocumentOut.from_model(d) for d in docs],
        limit=limit,
        offset=offset,
    )


async def delete_document(
    db: AsyncSession,
    *,
    document_public_id: uuid.UUID,
    garage_id: int,
) -> None:
    doc = await repo.soft_delete(db, public_id=document_public_id, garage_id=garage_id)
    if doc is None:
        raise DocumentNotFoundError(document_public_id)
    logger.info("document_deleted", public_id=str(document_public_id), garage_id=garage_id)


async def get_document(
    db: AsyncSession,
    *,
    document_public_id: uuid.UUID,
    garage_id: int,
) -> Document:
    doc = await repo.get_by_public_id(db, public_id=document_public_id, garage_id=garage_id)
    if doc is None:
        raise DocumentNotFoundError(document_public_id)
    return doc


async def archive_old_documents(db: AsyncSession) -> int:
    """Move documents older than CFG_DOCUMENT_ARCHIVE_AFTER_DAYS to archive S3 prefix.

    Returns the count of documents archived in this run.
    """
    cfg = get_settings()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=cfg.cfg_document_archive_after_days)
    archived_count = 0

    garage_ids = await repo.get_all_garage_ids(db)
    for garage_id in garage_ids:
        docs = await repo.get_archivable_documents(db, garage_id=garage_id, older_than=cutoff)
        for doc in docs:
            archive_key = f"archive/{doc.storage_key}"
            try:
                await storage.copy_object(
                    bucket=cfg.s3_bucket_documents,
                    source_key=doc.storage_key,
                    dest_key=archive_key,
                )
                await storage.delete_object(
                    bucket=cfg.s3_bucket_documents,
                    key=doc.storage_key,
                )
                # Update the row: new key + mark archived
                doc.storage_key = archive_key
                doc.archived = True
                doc.archived_at = datetime.now(tz=timezone.utc)
                await db.flush()
                archived_count += 1
                logger.info(
                    "document_archived",
                    public_id=str(doc.public_id),
                    garage_id=garage_id,
                    archive_key=archive_key,
                )
            except Exception:
                logger.exception(
                    "document_archive_error",
                    public_id=str(doc.public_id),
                    garage_id=garage_id,
                )
    if archived_count:
        await db.commit()
    return archived_count


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class FileTooLargeError(ValueError):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"File exceeds the maximum allowed size of {max_bytes} bytes")
        self.max_bytes = max_bytes


class MimeTypeNotAllowedError(ValueError):
    def __init__(
        self,
        mime: str,
        allowed: list[str],
        detail: str = "",
    ) -> None:
        msg = f"MIME type '{mime}' is not allowed"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)
        self.mime = mime
        self.allowed = allowed


class DocumentNotFoundError(ValueError):
    def __init__(self, public_id: uuid.UUID) -> None:
        super().__init__(f"Document '{public_id}' not found")
        self.public_id = public_id
