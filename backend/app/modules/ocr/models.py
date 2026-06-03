"""OCR extraction ORM model."""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import BigIntPK


class OcrStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    needs_review = "needs_review"


class OcrExtraction(Base):
    __tablename__ = "ocr_extraction"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engine_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="paddleocr-3"
    )
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # {field_name: value}
    structured_fields: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # {field_name: confidence_float}
    confidence_scores: Mapped[Optional[dict[str, float]]] = mapped_column(JSON, nullable=True)
    status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus, name="ocrextractionstatus"),
        nullable=False,
        default=OcrStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_ocr_extraction_status", "status"),
    )
