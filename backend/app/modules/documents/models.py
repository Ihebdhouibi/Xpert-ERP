"""Document ORM model — GED entry point."""
from __future__ import annotations

import enum
import uuid as uuid_lib
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import BigIntPK


class DocumentStatus(str, enum.Enum):
    active = "active"
    deleted = "deleted"


class DocumentCategory(str, enum.Enum):
    registration_card = "registration_card"
    id_doc = "id_doc"
    insurance = "insurance"
    accident_photo = "accident_photo"
    invoice = "invoice"
    supplier_invoice = "supplier_invoice"
    repair_attachment = "repair_attachment"
    generic = "generic"


class OwnerEntityType(str, enum.Enum):
    customer = "customer"
    vehicle = "vehicle"
    repair_order = "repair_order"
    invoice = "invoice"
    supplier_invoice = "supplier_invoice"
    generic = "generic"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid_lib.uuid4
    )
    garage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Polymorphic ownership — no FK constraint so modules are decoupled
    owner_entity_type: Mapped[str] = mapped_column(
        Enum(OwnerEntityType, name="owner_entity_type_enum"), nullable=False
    )
    owner_entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    category: Mapped[str] = mapped_column(
        Enum(DocumentCategory, name="document_category_enum"), nullable=False
    )

    # Original filename supplied by the uploader
    filename: Mapped[str] = mapped_column(String(512), nullable=False)

    # Detected / declared MIME type
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)

    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # SHA-256 hex digest for integrity verification
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Internal object-storage path — NEVER returned to clients
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Authorship
    uploaded_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum"),
        nullable=False,
        default=DocumentStatus.active,
        server_default="active",
    )

    __table_args__ = (
        Index("ix_document_garage_owner", "garage_id", "owner_entity_type", "owner_entity_id"),
        Index("ix_document_garage_category", "garage_id", "category"),
    )
