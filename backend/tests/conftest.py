"""Shared pytest fixtures for auth + RBAC tests."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import hash_password


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# In-memory-compatible test DB (SQLite async for unit tests)
# Use the DATABASE_URL env var for integration tests against real PG
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    """Seed a minimal role + permission + user."""
    perm = Permission(code="users.read", resource="users", action="read", description="")
    role = Role(code="admin", display_name="Administrator", is_system=True)
    db_session.add_all([perm, role])
    await db_session.flush()

    rp = RolePermission(role_id=role.id, permission_id=perm.id)
    db_session.add(rp)

    user = AppUser(
        garage_id=1,
        email="admin@test.com",
        full_name="Test Admin",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()

    ur = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(ur)
    await db_session.commit()
    return db_session


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    return redis


@pytest_asyncio.fixture
async def test_client(seeded_db: AsyncSession, mock_redis: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    app.dependency_overrides[get_db] = lambda: seeded_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
