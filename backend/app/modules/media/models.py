"""ORM models for inspection media (ro_media) and chunked upload sessions."""
from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK, JsonB


class RoMedia(Base):
    __tablename__ = "ro_media"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    inspection_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("inspection.id", ondelete="CASCADE"), nullable=True
    )
    ro_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="SET NULL"), nullable=True
    )
    uploader_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    # Internal S3 object key — never exposed to clients
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    archive_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("public_id", name="uq_ro_media_public_id"),
        Index("ix_ro_media_inspection", "inspection_id"),
        Index("ix_ro_media_ro", "ro_id"),
        Index("ix_ro_media_archive_sweep", "archived", "uploaded_at"),
    )


class MediaUploadSession(Base):
    """One row per in-flight chunked S3 multipart upload.

    The UUID primary key is also the public session identifier returned to clients.
    """

    __tablename__ = "ro_media_upload_session"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    inspection_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("inspection.id", ondelete="CASCADE"), nullable=True
    )
    ro_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("repair_order.id", ondelete="SET NULL"), nullable=True
    )
    uploader_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)

    # [{part_number: int, etag: str}] — appended as each chunk arrives
    received_parts: Mapped[Any] = mapped_column(JsonB, nullable=False, default=list)

    # The S3 object key for this upload (determined at session creation, used for all parts)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    s3_upload_id: Mapped[str] = mapped_column(Text, nullable=False)
    # pending | complete | aborted
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_ro_media_upload_session_inspection", "inspection_id"),
        Index("ix_ro_media_upload_session_expires", "expires_at"),
    )
