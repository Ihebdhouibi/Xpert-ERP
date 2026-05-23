"""Tests for the document upload module (M2 GED entry point)."""
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
from app.modules.auth.models import Permission, Role, RolePermission, UserRole
from app.modules.auth.service import create_access_token, hash_password
from app.modules.auth.models import AppUser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf(size: int = 512) -> bytes:
    """Minimal PDF-magic-byte payload of the requested size."""
    header = b"%PDF-1.4\n"
    return header + b"x" * max(0, size - len(header))


def _make_jpeg(size: int = 512) -> bytes:
    header = b"\xff\xd8\xff\xe0"
    return header + b"x" * max(0, size - len(header))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def doc_db(db_session: AsyncSession) -> AsyncSession:
    """Seed DB with a user + document permissions."""
    doc_upload_perm = Permission(
        code="document.upload", resource="document", action="upload", description=""
    )
    doc_download_perm = Permission(
        code="document.download", resource="document", action="download", description=""
    )
    role = Role(code="admin", display_name="Administrator", is_system=True)
    db_session.add_all([doc_upload_perm, doc_download_perm, role])
    await db_session.flush()

    db_session.add_all([
        RolePermission(role_id=role.id, permission_id=doc_upload_perm.id),
        RolePermission(role_id=role.id, permission_id=doc_download_perm.id),
    ])

    user = AppUser(
        garage_id=1,
        email="uploader@test.com",
        full_name="Upload Tester",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    await db_session.refresh(user)
    return db_session


@pytest.fixture
def mock_redis_doc() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    return redis


@pytest_asyncio.fixture
async def doc_client(
    doc_db: AsyncSession, mock_redis_doc: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield doc_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis_doc

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
        permissions=["document.upload", "document.download"],
        user_id=user_id,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------

class TestDocumentUpload:
    @patch("app.modules.documents.storage.upload_bytes", new_callable=AsyncMock)
    async def test_upload_pdf_success(
        self, mock_upload: AsyncMock, doc_client: AsyncClient, doc_db: AsyncSession
    ) -> None:
        """A valid PDF uploads and returns metadata without storage_key."""
        mock_upload.return_value = None

        # Get user id from the seeded DB
        from sqlalchemy import select
        from app.modules.auth.models import AppUser as AU
        result = await doc_db.execute(select(AU).where(AU.email == "uploader@test.com"))
        user = result.scalar_one()

        pdf_content = _make_pdf(1024)
        resp = await doc_client.post(
            "/api/v1/documents",
            headers=_auth_header(user.id),
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"category": "generic", "owner_entity_type": "generic"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["filename"] == "test.pdf"
        assert body["mime_type"] == "application/pdf"
        assert body["size_bytes"] == len(pdf_content)
        assert "storage_key" not in body
        assert "id" in body
        mock_upload.assert_awaited_once()

    @patch("app.modules.documents.storage.upload_bytes", new_callable=AsyncMock)
    async def test_upload_rejects_disallowed_mime(
        self, mock_upload: AsyncMock, doc_client: AsyncClient, doc_db: AsyncSession
    ) -> None:
        """A file with a disallowed MIME type is rejected with 415."""
        from sqlalchemy import select
        from app.modules.auth.models import AppUser as AU
        result = await doc_db.execute(select(AU).where(AU.email == "uploader@test.com"))
        user = result.scalar_one()

        resp = await doc_client.post(
            "/api/v1/documents",
            headers=_auth_header(user.id),
            files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00" + b"x" * 100), "application/octet-stream")},
            data={"category": "generic", "owner_entity_type": "generic"},
        )

        assert resp.status_code == 415
        mock_upload.assert_not_awaited()

    @patch("app.modules.documents.storage.upload_bytes", new_callable=AsyncMock)
    async def test_upload_rejects_oversized_file(
        self, mock_upload: AsyncMock, doc_client: AsyncClient, doc_db: AsyncSession
    ) -> None:
        """Files larger than CFG_MAX_UPLOAD_SIZE_BYTES are rejected with 413."""
        from sqlalchemy import select
        from app.modules.auth.models import AppUser as AU
        result = await doc_db.execute(select(AU).where(AU.email == "uploader@test.com"))
        user = result.scalar_one()

        # Override the limit to a tiny value for the test
        from app.core.config import get_settings
        original = get_settings().max_upload_size_bytes
        get_settings().max_upload_size_bytes = 10  # type: ignore[misc]

        try:
            resp = await doc_client.post(
                "/api/v1/documents",
                headers=_auth_header(user.id),
                files={"file": ("big.pdf", io.BytesIO(_make_pdf(100)), "application/pdf")},
                data={"category": "generic", "owner_entity_type": "generic"},
            )
            assert resp.status_code == 413
        finally:
            get_settings().max_upload_size_bytes = original  # type: ignore[misc]

        mock_upload.assert_not_awaited()

    async def test_upload_requires_auth(self, doc_client: AsyncClient) -> None:
        """Unauthenticated upload attempt returns 401/403."""
        resp = await doc_client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
            data={"category": "generic", "owner_entity_type": "generic"},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Signed URL tests
# ---------------------------------------------------------------------------

class TestSignedUrl:
    @patch("app.modules.documents.storage.upload_bytes", new_callable=AsyncMock)
    @patch("app.modules.documents.storage.generate_presigned_url", new_callable=AsyncMock)
    async def test_signed_url_returned(
        self,
        mock_presign: AsyncMock,
        mock_upload: AsyncMock,
        doc_client: AsyncClient,
        doc_db: AsyncSession,
    ) -> None:
        """Uploading a document then requesting a signed URL returns a URL."""
        mock_upload.return_value = None
        mock_presign.return_value = "https://minio.example.com/bucket/key?sig=abc"

        from sqlalchemy import select
        from app.modules.auth.models import AppUser as AU
        result = await doc_db.execute(select(AU).where(AU.email == "uploader@test.com"))
        user = result.scalar_one()
        headers = _auth_header(user.id)

        # Upload
        resp = await doc_client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": ("doc.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
            data={"category": "generic", "owner_entity_type": "generic"},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        # Get signed URL
        url_resp = await doc_client.get(
            f"/api/v1/documents/{doc_id}/signed-url",
            headers=headers,
        )
        assert url_resp.status_code == 200
        body = url_resp.json()
        assert "url" in body
        assert "storage_key" not in body
        assert body["document_id"] == doc_id
        assert body["expires_in_seconds"] > 0

    async def test_signed_url_not_found(
        self, doc_client: AsyncClient, doc_db: AsyncSession
    ) -> None:
        """Requesting a signed URL for a non-existent document returns 404."""
        from sqlalchemy import select
        from app.modules.auth.models import AppUser as AU
        result = await doc_db.execute(select(AU).where(AU.email == "uploader@test.com"))
        user = result.scalar_one()

        resp = await doc_client.get(
            f"/api/v1/documents/{uuid.uuid4()}/signed-url",
            headers=_auth_header(user.id),
        )
        assert resp.status_code == 404
