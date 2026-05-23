"""Document router — POST /documents and GET /documents/{id}/signed-url."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.documents import service
from app.modules.documents.models import DocumentCategory, OwnerEntityType
from app.modules.documents.schemas import DocumentOut, SignedUrlResponse
from app.modules.documents.service import (
    DocumentNotFoundError,
    FileTooLargeError,
    MimeTypeNotAllowedError,
)
from app.modules.rbac.dependencies import AuthUser, require_permission

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission("document.upload")],
    summary="Upload a document to object storage",
)
async def upload_document(
    user: AuthUser,
    file: UploadFile,
    category: DocumentCategory = Form(...),
    owner_entity_type: OwnerEntityType = Form(...),
    owner_entity_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """Multipart upload.  Returns document metadata; storage key is never exposed."""
    try:
        return await service.upload_document(
            db,
            file=file,
            category=category,
            owner_entity_type=owner_entity_type,
            owner_entity_id=owner_entity_id,
            garage_id=user.garage_id,
            uploaded_by=user.user_id,
        )
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except MimeTypeNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please try again later.",
        ) from exc


@router.get(
    "/{document_id}/signed-url",
    response_model=SignedUrlResponse,
    dependencies=[require_permission("document.download")],
    summary="Get a short-lived pre-signed download URL",
)
async def get_signed_url(
    document_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> SignedUrlResponse:
    """Returns a pre-signed URL valid for the configured expiry window.
    The storage key is never returned — only the time-limited URL.
    """
    try:
        return await service.get_signed_url(
            db,
            document_public_id=document_id,
            garage_id=user.garage_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please try again later.",
        ) from exc
