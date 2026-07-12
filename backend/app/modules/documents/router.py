"""Document router — POST /documents and GET /documents/{id}/signed-url."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.documents import service
from app.modules.documents.models import DocumentCategory, OwnerEntityType
from app.modules.documents.schemas import DocumentListResponse, DocumentOut, SignedUrlResponse
from app.modules.documents.service import (
    DocumentNotFoundError,
    FileTooLargeError,
    MimeTypeNotAllowedError,
)
from app.modules.rbac.dependencies import AuthUser, require_permission
from app.core.logging import get_logger

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger("documents.router")


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
    background_tasks: BackgroundTasks,
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
            background_tasks=background_tasks,
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
    "",
    response_model=DocumentListResponse,
    dependencies=[require_permission("document.read")],
    summary="List documents with optional filters and full-text search",
)
async def list_documents(
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
    category: Optional[DocumentCategory] = Query(None),
    owner_entity_type: Optional[OwnerEntityType] = Query(None),
    owner_entity_id: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    q: Optional[str] = Query(None, description="Full-text search on filename and extracted text"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> DocumentListResponse:
    return await service.list_documents(
        db,
        garage_id=user.garage_id,
        category=category,
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        from_date=from_date,
        to_date=to_date,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentOut,
    dependencies=[require_permission("document.read")],
    summary="Get document metadata by public ID",
)
async def get_document(
    document_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    try:
        doc = await service.get_document(db, document_public_id=document_id, garage_id=user.garage_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentOut.from_model(doc)


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


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[require_permission("document.delete")],
    summary="Soft-delete a document",
)
async def delete_document(
    document_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.delete_document(
            db,
            document_public_id=document_id,
            garage_id=user.garage_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}/owner-supplier",
    dependencies=[require_permission("document.read")],
    summary="Resolve the supplier linked as owner of a document (service_invoice flow)",
)
async def get_document_owner_supplier(
    document_id: uuid.UUID,
    user: AuthUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the supplier name when the document is filed under a supplier entity."""
    from sqlalchemy import select as sa_select
    from app.modules.supplier.models import Supplier
    from app.modules.documents import repository as doc_repo

    doc = await doc_repo.get_by_public_id(db, public_id=document_id, garage_id=user.garage_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.owner_entity_type != OwnerEntityType.supplier or not doc.owner_entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document is not filed under a supplier")
    sup_res = await db.execute(
        sa_select(Supplier).where(
            Supplier.id == doc.owner_entity_id,
            Supplier.garage_id == user.garage_id,
        )
    )
    sup = sup_res.scalar_one_or_none()
    if sup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return {
        "supplier_id": str(sup.public_id),
        "supplier_int_id": sup.id,
        "supplier_name": sup.name,
    }
