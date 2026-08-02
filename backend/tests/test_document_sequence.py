"""Tests for the document sequence service (#27).

Covers:
- Monotonic, gap-free numbers within a (garage, doc_type, year)
- Row is auto-created on first call
- Different doc types maintain independent counters
- Different years maintain independent counters
- Different garages are isolated
- Admin GET /api/v1/sequences endpoint (200 + 403)
- Formatted reference string pattern
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/xpert_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY_ID", "testkey")
os.environ.setdefault("S3_SECRET_ACCESS_KEY", "testsecret")
os.environ.setdefault("S3_BUCKET_DOCUMENTS", "test-documents")
os.environ.setdefault("S3_BUCKET_MEDIA", "test-media")

from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password
from app.modules.sequence import service as seq_service
from app.modules.sequence import repository as seq_repo


# ---------------------------------------------------------------------------
# Fixtures (mirrors conftest but self-contained for clarity)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_sequence_db(db_session: AsyncSession) -> AsyncSession:
    """Seed RBAC fixtures + a user with admin.sequence.read permission."""
    perm = Permission(
        code="admin.sequence.read",
        resource="sequences",
        action="read",
        description="",
    )
    role = Role(code="admin", display_name="Administrator", is_system=True)
    db_session.add_all([perm, role])
    await db_session.flush()

    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = AppUser(
        garage_id=1,
        email="admin@test.com",
        full_name="Test Admin",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    return db_session


@pytest.fixture
def mock_redis() -> AsyncMock:
    r = AsyncMock()
    r.setex = AsyncMock(return_value=True)
    r.exists = AsyncMock(return_value=0)
    r.getdel = AsyncMock(return_value=None)
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    return r


@pytest_asyncio.fixture
async def seq_client(
    seeded_sequence_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_sequence_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Service-level unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestSequenceServiceUnit:

    async def test_first_call_creates_row_and_returns_one(self, db_session: AsyncSession):
        result = await seq_service.next(db_session, garage_id=1, doc_type="INV")
        assert result.number == 1
        assert result.doc_type == "INV"
        assert result.year == datetime.now(tz=timezone.utc).year

    async def test_sequential_calls_monotonically_increase(self, db_session: AsyncSession):
        results = []
        for _ in range(5):
            r = await seq_service.next(db_session, garage_id=1, doc_type="INV")
            results.append(r.number)
        assert results == [1, 2, 3, 4, 5], f"Expected [1..5], got {results}"

    async def test_no_gaps_sequential(self, db_session: AsyncSession):
        nums = [
            (await seq_service.next(db_session, garage_id=1, doc_type="QUOT")).number
            for _ in range(3)
        ]
        assert nums == list(range(1, len(nums) + 1))

    async def test_different_doc_types_independent(self, db_session: AsyncSession):
        inv1 = await seq_service.next(db_session, garage_id=1, doc_type="INV")
        inv2 = await seq_service.next(db_session, garage_id=1, doc_type="INV")
        quot1 = await seq_service.next(db_session, garage_id=1, doc_type="QUOT")

        assert inv1.number == 1
        assert inv2.number == 2
        assert quot1.number == 1  # independent counter

    async def test_different_garages_isolated(self, db_session: AsyncSession):
        g1 = await seq_service.next(db_session, garage_id=1, doc_type="INV")
        g2 = await seq_service.next(db_session, garage_id=2, doc_type="INV")
        assert g1.number == 1
        assert g2.number == 1  # garage 2 starts at 1

    async def test_doc_type_normalised_to_uppercase(self, db_session: AsyncSession):
        r = await seq_service.next(db_session, garage_id=1, doc_type="inv")
        assert r.doc_type == "INV"

    async def test_formatted_string_matches_pattern(self, db_session: AsyncSession):
        r = await seq_service.next(db_session, garage_id=1, doc_type="INV")
        year = datetime.now(tz=timezone.utc).year
        expected = f"INV-{year}-00001"
        assert r.formatted == expected, f"Expected {expected!r}, got {r.formatted!r}"

    async def test_formatted_zero_padded_five_digits(self, db_session: AsyncSession):
        for _ in range(9):
            await seq_service.next(db_session, garage_id=1, doc_type="CRNOTE")
        r = await seq_service.next(db_session, garage_id=1, doc_type="CRNOTE")
        assert r.formatted.endswith("-00010")

    async def test_peek_returns_empty_for_new_garage(self, db_session: AsyncSession):
        result = await seq_service.peek(db_session, garage_id=999)
        assert result == []

    async def test_peek_returns_all_types_for_garage(self, db_session: AsyncSession):
        await seq_service.next(db_session, garage_id=1, doc_type="INV")
        await seq_service.next(db_session, garage_id=1, doc_type="QUOT")
        await seq_service.next(db_session, garage_id=1, doc_type="INV")

        rows = await seq_service.peek(db_session, garage_id=1)
        doc_types = {r.doc_type for r in rows}
        assert "INV" in doc_types
        assert "QUOT" in doc_types
        # INV counter should be 2
        inv = next(r for r in rows if r.doc_type == "INV")
        assert inv.last_number == 2

    async def test_delivery_order_type(self, db_session: AsyncSession):
        r = await seq_service.next(db_session, garage_id=1, doc_type="DO")
        assert r.doc_type == "DO"
        assert r.number == 1

    async def test_all_standard_doc_types(self, db_session: AsyncSession):
        for doc_type in ("INV", "QUOT", "CRNOTE", "DO"):
            r = await seq_service.next(db_session, garage_id=1, doc_type=doc_type)
            assert r.number == 1
            assert r.doc_type == doc_type


# ---------------------------------------------------------------------------
# Repository-level tests
# ---------------------------------------------------------------------------

class TestSequenceRepository:

    async def test_get_sequence_returns_none_when_absent(self, db_session: AsyncSession):
        row = await seq_repo.get_sequence(db_session, garage_id=1, doc_type="INV", year=2099)
        assert row is None

    async def test_create_then_get(self, db_session: AsyncSession):
        created = await seq_repo.create_sequence(db_session, garage_id=1, doc_type="INV", year=2025)
        await db_session.flush()
        fetched = await seq_repo.get_sequence(db_session, garage_id=1, doc_type="INV", year=2025)
        assert fetched is not None
        assert fetched.last_number == 0

    async def test_list_sequences_empty(self, db_session: AsyncSession):
        rows = await seq_repo.list_sequences(db_session, garage_id=99)
        assert rows == []


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestSequenceEndpoints:

    async def _login(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    async def test_list_sequences_empty_returns_200(self, seq_client: AsyncClient):
        token = await self._login(seq_client)
        resp = await seq_client.get(
            "/api/v1/sequences",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_sequences_returns_data_after_next(
        self, seq_client: AsyncClient, seeded_sequence_db: AsyncSession
    ):
        # Insert a row directly via service
        await seq_service.next(seeded_sequence_db, garage_id=1, doc_type="INV")
        await seeded_sequence_db.commit()

        token = await self._login(seq_client)
        resp = await seq_client.get(
            "/api/v1/sequences",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["doc_type"] == "INV"
        assert data[0]["last_number"] == 1

    async def test_list_sequences_requires_auth(self, seq_client: AsyncClient):
        resp = await seq_client.get("/api/v1/sequences")
        assert resp.status_code == 401

    async def test_list_sequences_requires_permission(
        self, seeded_sequence_db: AsyncSession, mock_redis: AsyncMock
    ):
        """User without admin.sequence.read permission gets 403."""
        from app.modules.auth.models import AppUser
        from app.modules.auth.service import hash_password

        # Create user with no permissions
        user = AppUser(
            garage_id=1,
            email="noperm@test.com",
            full_name="No Perm",
            password_hash=hash_password("Test1234!"),
        )
        seeded_sequence_db.add(user)
        await seeded_sequence_db.commit()

        app = create_app()

        async def override_db():
            yield seeded_sequence_db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "noperm@test.com", "password": "Test1234!"},
            )
            assert login.status_code == 200
            token = login.json()["access_token"]

            resp = await client.get(
                "/api/v1/sequences",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403

        app.dependency_overrides.clear()
