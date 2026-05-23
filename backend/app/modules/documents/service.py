"""Document service — validation, upload orchestration, signed-URL generation."""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.documents import repository as repo
from app.modules.documents import storage
from app.modules.documents.models import Document, DocumentCategory, OwnerEntityType
from app.modules.documents.schemas import DocumentOut, SignedUrlResponse

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
