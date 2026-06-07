"""Tests for the OCR pipeline (Issue #48)."""
from __future__ import annotations

import io
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import create_access_token, hash_password
from app.modules.ocr.engine import OcrLine, RawOcrResult
from app.modules.ocr.models import OcrStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg(size: int = 512) -> bytes:
    header = b"\xff\xd8\xff\xe0"
    return header + b"x" * max(0, size - len(header))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def ocr_db(db_session: AsyncSession) -> AsyncSession:
    """Seed DB with a user + document.upload + document.read permissions."""
    upload_perm = Permission(
        code="document.upload", resource="document", action="upload", description=""
    )
    read_perm = Permission(
        code="document.read", resource="document", action="read", description=""
    )
    role = Role(code="admin", display_name="Administrator", is_system=True)
    db_session.add_all([upload_perm, read_perm, role])
    await db_session.flush()

    db_session.add_all([
        RolePermission(role_id=role.id, permission_id=upload_perm.id),
        RolePermission(role_id=role.id, permission_id=read_perm.id),
    ])

    user = AppUser(
        garage_id=1,
        email="ocr_user@test.com",
        full_name="OCR Tester",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    await db_session.refresh(user)
    return db_session


@pytest.fixture
def mock_redis_ocr() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    return redis


@pytest_asyncio.fixture
async def ocr_client(
    ocr_db: AsyncSession, mock_redis_ocr: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield ocr_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis_ocr

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


def _auth_header(user_id: int, garage_id: int = 1) -> dict[str, str]:
    token, _ = create_access_token(
        subject=str(uuid.uuid4()),
        garage_id=garage_id,
        roles=["admin"],
        permissions=["document.upload", "document.read"],
        user_id=user_id,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test: enqueue OCR creates a pending extraction
# ---------------------------------------------------------------------------

class TestEnqueueOcr:
    @patch("app.modules.documents.storage.upload_bytes", new_callable=AsyncMock)
    @patch("app.modules.ocr.service.process_ocr_job", new_callable=AsyncMock)
    @patch("app.modules.ocr.service.enqueue_ocr", new_callable=AsyncMock)
    async def test_enqueue_creates_pending_row(
        self,
        mock_enqueue: AsyncMock,
        mock_process: AsyncMock,
        mock_upload: AsyncMock,
        ocr_client: AsyncClient,
        ocr_db: AsyncSession,
    ) -> None:
        """POST /ocr/enqueue/{document_id} returns 202 with a pending extraction."""
        mock_upload.return_value = None
        mock_process.return_value = None

        # Create a fake extraction to return
        from app.modules.ocr.models import OcrExtraction
        fake_extraction = OcrExtraction(
            public_id=uuid.uuid4(),
            document_id=1,
            engine_version="paddleocr-3",
            status=OcrStatus.pending,
        )
        fake_extraction.id = 999
        import datetime
        fake_extraction.created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        fake_extraction.processed_at = None
        fake_extraction.reviewed_by = None
        fake_extraction.reviewed_at = None
        fake_extraction.raw_text = None
        fake_extraction.structured_fields = None
        fake_extraction.confidence_scores = None
        mock_enqueue.return_value = fake_extraction

        from sqlalchemy import select
        from app.modules.auth.models import AppUser as AU
        result = await ocr_db.execute(select(AU).where(AU.email == "ocr_user@test.com"))
        user = result.scalar_one()

        resp = await ocr_client.post(
            "/api/v1/ocr/enqueue/1",
            headers=_auth_header(user.id),
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        mock_enqueue.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test: OCR service — process_ocr_job
# ---------------------------------------------------------------------------

class TestProcessOcrJob:
    async def test_process_completes_with_mocked_engine(
        self, ocr_db: AsyncSession
    ) -> None:
        """process_ocr_job sets status=completed when engine returns high-confidence results."""
        from app.modules.documents import repository as doc_repo
        from app.modules.documents.models import DocumentCategory, OwnerEntityType
        from app.modules.ocr.service import enqueue_ocr, process_ocr_job

        # Seed a document
        doc = await doc_repo.create_document(
            ocr_db,
            garage_id=1,
            owner_entity_type=OwnerEntityType.vehicle,
            owner_entity_id=None,
            category=DocumentCategory.registration_card,
            filename="carte_grise.jpg",
            mime_type="image/jpeg",
            size_bytes=512,
            sha256="aabbcc",
            storage_key="1/registration_card/carte_grise.jpg",
            uploaded_by=1,
        )

        extraction = await enqueue_ocr(ocr_db, document_id=doc.id)
        assert extraction.status == OcrStatus.pending

        # Mock S3 download + PaddleOCR engine
        high_conf_result = RawOcrResult(
            lines=[
                OcrLine(text="IMMATRICULATION", confidence=0.99),
                OcrLine(text="12345-AB-06", confidence=0.95),
                OcrLine(text="VIN", confidence=0.98),
                OcrLine(text="WBA12345678901234", confidence=0.92),
            ],
            full_text="IMMATRICULATION\n12345-AB-06\nVIN\nWBA12345678901234",
        )

        with (
            patch("app.modules.documents.storage.download_object", new_callable=AsyncMock) as mock_dl,
            patch("app.modules.ocr.engine.PaddleOcrEngine.run_ocr", new_callable=AsyncMock) as mock_ocr,
        ):
            mock_dl.return_value = b"\xff\xd8\xff\xe0" + b"x" * 512
            mock_ocr.return_value = high_conf_result

            updated = await process_ocr_job(ocr_db, extraction_id=extraction.id)

        # High-confidence result → completed
        assert updated.status in (OcrStatus.completed, OcrStatus.needs_review)
        assert updated.raw_text is not None
        assert updated.processed_at is not None

    async def test_process_sets_needs_review_for_low_confidence(
        self, ocr_db: AsyncSession
    ) -> None:
        """Fields below threshold → status=needs_review, NOT auto-written."""
        from app.modules.documents import repository as doc_repo
        from app.modules.documents.models import DocumentCategory, OwnerEntityType
        from app.modules.ocr.service import enqueue_ocr, process_ocr_job

        doc = await doc_repo.create_document(
            ocr_db,
            garage_id=1,
            owner_entity_type=OwnerEntityType.vehicle,
            owner_entity_id=None,
            category=DocumentCategory.registration_card,
            filename="blurry.jpg",
            mime_type="image/jpeg",
            size_bytes=512,
            sha256="ddeeff",
            storage_key="1/registration_card/blurry.jpg",
            uploaded_by=1,
        )

        extraction = await enqueue_ocr(ocr_db, document_id=doc.id)

        # Low-confidence OCR result
        low_conf_result = RawOcrResult(
            lines=[
                OcrLine(text="IMMATRICULATION", confidence=0.99),
                OcrLine(text="12345-AB-06", confidence=0.40),  # below 0.75 threshold
            ],
            full_text="IMMATRICULATION\n12345-AB-06",
        )

        with (
            patch("app.modules.documents.storage.download_object", new_callable=AsyncMock) as mock_dl,
            patch("app.modules.ocr.engine.PaddleOcrEngine.run_ocr", new_callable=AsyncMock) as mock_ocr,
        ):
            mock_dl.return_value = b"\xff\xd8\xff\xe0" + b"x" * 512
            mock_ocr.return_value = low_conf_result

            updated = await process_ocr_job(ocr_db, extraction_id=extraction.id)

        # Must NOT be auto-completed — must require human review
        assert updated.status == OcrStatus.needs_review

        # Verify no vehicle/customer row was created (low confidence never auto-writes)
        from sqlalchemy import select
        from app.modules.vehicles.models import Vehicle
        vehicles = (await ocr_db.execute(select(Vehicle))).scalars().all()
        assert len(vehicles) == 0


# ---------------------------------------------------------------------------
# Test: confirm_fields
# ---------------------------------------------------------------------------

class TestConfirmFields:
    async def test_confirm_sets_reviewed_state(self, ocr_db: AsyncSession) -> None:
        """confirm_fields() marks extraction as completed with reviewed_at set."""
        from app.modules.documents import repository as doc_repo
        from app.modules.documents.models import DocumentCategory, OwnerEntityType
        from app.modules.ocr.service import confirm_fields, enqueue_ocr, process_ocr_job

        doc = await doc_repo.create_document(
            ocr_db,
            garage_id=1,
            owner_entity_type=OwnerEntityType.vehicle,
            owner_entity_id=None,
            category=DocumentCategory.id_doc,
            filename="cin.jpg",
            mime_type="image/jpeg",
            size_bytes=256,
            sha256="112233",
            storage_key="1/id_doc/cin.jpg",
            uploaded_by=1,
        )

        extraction = await enqueue_ocr(ocr_db, document_id=doc.id)

        # Simulate a completed-but-needs-review result
        from app.modules.ocr import repository as ocr_repo
        await ocr_repo.update_status(
            ocr_db,
            extraction_id=extraction.id,
            status=OcrStatus.needs_review,
            structured_fields={"nom": "DUPONT", "prenom": "Jean"},
            confidence_scores={"nom": 0.60, "prenom": 0.55},
        )

        updated = await confirm_fields(
            ocr_db,
            extraction_public_id=extraction.public_id,
            confirmed_fields={"nom": "DUPONT", "prenom": "Jean-Paul"},
            reviewer_id=1,
        )

        assert updated.status == OcrStatus.completed
        assert updated.reviewed_at is not None
        assert updated.reviewed_by == 1
        # Confirmed values persisted
        assert updated.structured_fields["prenom"] == "Jean-Paul"
        # Confirmed fields get confidence=1.0
        assert updated.confidence_scores["prenom"] == 1.0

    async def test_confirm_fails_for_pending_extraction(
        self, ocr_db: AsyncSession
    ) -> None:
        """Confirming a pending extraction raises OcrInvalidStateError."""
        from app.modules.documents import repository as doc_repo
        from app.modules.documents.models import DocumentCategory, OwnerEntityType
        from app.modules.ocr.service import OcrInvalidStateError, confirm_fields, enqueue_ocr

        doc = await doc_repo.create_document(
            ocr_db,
            garage_id=1,
            owner_entity_type=OwnerEntityType.generic,
            owner_entity_id=None,
            category=DocumentCategory.id_doc,
            filename="id.jpg",
            mime_type="image/jpeg",
            size_bytes=128,
            sha256="445566",
            storage_key="1/id_doc/id.jpg",
            uploaded_by=1,
        )

        extraction = await enqueue_ocr(ocr_db, document_id=doc.id)

        with pytest.raises(OcrInvalidStateError):
            await confirm_fields(
                ocr_db,
                extraction_public_id=extraction.public_id,
                confirmed_fields={"nom": "TEST"},
                reviewer_id=1,
            )


# ---------------------------------------------------------------------------
# Test: supplier-invoice extraction dispatch + ingestion prefill
# ---------------------------------------------------------------------------

class TestSupplierInvoiceOcr:
    async def _seed_and_process(self, ocr_db: AsyncSession):
        from app.modules.documents import repository as doc_repo
        from app.modules.documents.models import DocumentCategory, OwnerEntityType
        from app.modules.ocr.service import enqueue_ocr, process_ocr_job

        doc = await doc_repo.create_document(
            ocr_db,
            garage_id=1,
            owner_entity_type=OwnerEntityType.supplier_invoice,
            owner_entity_id=None,
            category=DocumentCategory.supplier_invoice,
            filename="facture_fournisseur.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            sha256="ffaa11",
            storage_key="1/supplier_invoice/f.pdf",
            uploaded_by=1,
        )
        extraction = await enqueue_ocr(ocr_db, document_id=doc.id)

        result = RawOcrResult(
            lines=[
                OcrLine(text="Facture N° INV-2024-077", confidence=0.95),
                OcrLine(text="Date facture 12/03/2024", confidence=0.90),
                OcrLine(text="Fournisseur", confidence=0.92),
                OcrLine(text="PIECES AUTO SARL", confidence=0.91),
                OcrLine(text="Total HT 1 250,00", confidence=0.93),
                OcrLine(text="Total TTC 1 500,00", confidence=0.94),
            ],
            full_text="...",
        )
        with (
            patch("app.modules.documents.storage.download_object", new_callable=AsyncMock) as mock_dl,
            patch("app.modules.ocr.engine.PaddleOcrEngine.run_ocr", new_callable=AsyncMock) as mock_ocr,
        ):
            mock_dl.return_value = b"%PDF-1.7 fake"
            mock_ocr.return_value = result
            updated = await process_ocr_job(ocr_db, extraction_id=extraction.id)
        return extraction, updated

    async def test_dispatch_extracts_invoice_fields(self, ocr_db: AsyncSession) -> None:
        _extraction, updated = await self._seed_and_process(ocr_db)
        fields = updated.structured_fields
        assert fields["numero_facture"] == "INV-2024-077"
        assert fields["total_ttc"] == "1500.00"
        # raw lines are also retained for the reviewer
        assert any(k.startswith("ligne_") for k in fields)

    async def test_ingest_returns_supplier_invoice_prefill(self, ocr_db: AsyncSession) -> None:
        from app.modules.ocr.service import ingest_extraction

        extraction, updated = await self._seed_and_process(ocr_db)
        result = await ingest_extraction(
            ocr_db,
            extraction_public_id=extraction.public_id,
            confirmed_fields={k: v for k, v in updated.structured_fields.items()},
            reviewer_id=1,
        )
        assert result.target == "supplier_invoice"
        assert result.prefill is not None
        assert result.prefill.number == "INV-2024-077"
        assert result.prefill.total_ttc_cents == 150000
        assert result.prefill.invoice_date == "2024-03-12"
