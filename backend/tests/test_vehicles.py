"""Tests for the vehicle module endpoints."""
from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Env vars must be set before any app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/xpert_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY_ID", "testkey")
os.environ.setdefault("S3_SECRET_ACCESS_KEY", "testsecret")
os.environ.setdefault("S3_BUCKET_DOCUMENTS", "test-documents")
os.environ.setdefault("S3_BUCKET_MEDIA", "test-media")

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.auth.service import create_access_token, hash_password

GARAGE_ID = 1
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures (scoped per function to keep tests isolated)
# ---------------------------------------------------------------------------

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
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    """Seed roles, permissions and a user who can interact with vehicles."""
    vehicle_perms = [
        ("vehicle.create", "vehicle", "create"),
        ("vehicle.read", "vehicle", "read"),
        ("vehicle.update", "vehicle", "update"),
        ("vehicle.delete", "vehicle", "delete"),
    ]
    perms = [
        Permission(code=code, resource=res, action=act, description="")
        for code, res, act in vehicle_perms
    ]
    role = Role(code="garage_admin", display_name="Garage Admin", is_system=False)
    db_session.add_all([*perms, role])
    await db_session.flush()

    for p in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=p.id))

    user = AppUser(
        garage_id=GARAGE_ID,
        email="admin@garage.com",
        full_name="Garage Admin",
        password_hash=hash_password("Test1234!"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    return db_session


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.getdel = AsyncMock(return_value=None)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest_asyncio.fixture
async def auth_client(
    seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client pre-authorised with all vehicle permissions."""
    app = create_app()

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    token, _ = create_access_token(
        subject="00000000-0000-0000-0000-000000000001",
        garage_id=GARAGE_ID,
        roles=["garage_admin"],
        permissions=["vehicle.create", "vehicle.read", "vehicle.update", "vehicle.delete"],
        user_id=1,
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "/api/v1/vehicles"

CREATE_BODY = {
    "registration": "ABC-123",
    "make": "Toyota",
    "model": "Corolla",
    "year": 2020,
    "fuel_type": "gasoline",
}

CREATE_VIN_ONLY = {
    "vin": "1HGBH41JXMN109186",
    "make": "Honda",
    "model": "Civic",
}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_create_vehicle_with_registration(auth_client: AsyncClient) -> None:
    r = await auth_client.post(BASE, json=CREATE_BODY)
    assert r.status_code == 201
    data = r.json()
    assert data["registration"] == "ABC-123"
    assert data["make"] == "Toyota"
    assert data["status"] == "active"
    assert data["version"] == 0


async def test_create_vehicle_vin_only(auth_client: AsyncClient) -> None:
    r = await auth_client.post(BASE, json=CREATE_VIN_ONLY)
    assert r.status_code == 201
    data = r.json()
    assert data["vin"] == "1HGBH41JXMN109186"
    assert data["registration"] is None


async def test_create_vehicle_neither_reg_nor_vin_returns_422(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        BASE, json={"make": "BMW", "model": "X5"}
    )
    assert r.status_code == 422


async def test_create_duplicate_registration_returns_409(auth_client: AsyncClient) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)
    r = await auth_client.post(BASE, json=CREATE_BODY)
    assert r.status_code == 409


async def test_create_duplicate_vin_returns_409(auth_client: AsyncClient) -> None:
    await auth_client.post(BASE, json=CREATE_VIN_ONLY)
    r = await auth_client.post(BASE, json=CREATE_VIN_ONLY)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Get / List
# ---------------------------------------------------------------------------

async def test_get_vehicle_by_id(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.get(f"{BASE}/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


async def test_get_unknown_vehicle_returns_404(auth_client: AsyncClient) -> None:
    r = await auth_client.get(f"{BASE}/99999")
    assert r.status_code == 404


async def test_list_vehicles_empty(auth_client: AsyncClient) -> None:
    r = await auth_client.get(BASE)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


async def test_list_vehicles_search_by_registration(auth_client: AsyncClient) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)
    r = await auth_client.get(BASE, params={"q": "ABC"})
    assert r.status_code == 200
    assert r.json()["total"] == 1


async def test_list_vehicles_search_no_match(auth_client: AsyncClient) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)
    r = await auth_client.get(BASE, params={"q": "ZZZ"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def test_update_vehicle(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.patch(
        f"{BASE}/{created['id']}",
        json={"color": "red", "mileage_current": 50000},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["color"] == "red"
    assert data["mileage_current"] == 50000
    assert data["version"] == 1


async def test_update_vehicle_correct_version_header(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.patch(
        f"{BASE}/{created['id']}",
        json={"color": "blue"},
        headers={"If-Match": "0"},
    )
    assert r.status_code == 200
    assert r.json()["version"] == 1


async def test_update_vehicle_wrong_version_returns_409(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.patch(
        f"{BASE}/{created['id']}",
        json={"color": "blue"},
        headers={"If-Match": "99"},
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------

async def test_delete_vehicle(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.delete(f"{BASE}/{created['id']}")
    assert r.status_code == 204

    # Should not be findable afterwards
    r2 = await auth_client.get(f"{BASE}/{created['id']}")
    assert r2.status_code == 404


async def test_delete_unknown_vehicle_returns_404(auth_client: AsyncClient) -> None:
    r = await auth_client.delete(f"{BASE}/99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Ownership transfer
# ---------------------------------------------------------------------------

async def test_ownership_transfer(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.post(
        f"{BASE}/{created['id']}/transfer-ownership",
        json={"new_customer_id": 42, "note": "Sold at auction"},
    )
    assert r.status_code == 200
    assert r.json()["customer_id"] == 42


async def test_ownership_release(auth_client: AsyncClient) -> None:
    """Transfer with new_customer_id=None releases the vehicle from any owner."""
    body = {**CREATE_BODY, "registration": "XYZ-999", "customer_id": 42}
    created = (await auth_client.post(BASE, json=body)).json()
    r = await auth_client.post(
        f"{BASE}/{created['id']}/transfer-ownership",
        json={"new_customer_id": None},
    )
    assert r.status_code == 200
    assert r.json()["customer_id"] is None


# ---------------------------------------------------------------------------
# Re-registration
# ---------------------------------------------------------------------------

async def test_re_register_vehicle(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    r = await auth_client.post(
        f"{BASE}/{created['id']}/re-register",
        json={"new_registration": "NEW-456", "note": "Plate changed"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["registration"] == "NEW-456"


async def test_re_register_conflict_with_other_vehicle_returns_409(
    auth_client: AsyncClient,
) -> None:
    """New registration already belongs to a different vehicle → 409."""
    v1 = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    v2 = (
        await auth_client.post(
            BASE, json={**CREATE_BODY, "registration": "NEW-456"}
        )
    ).json()
    r = await auth_client.post(
        f"{BASE}/{v1['id']}/re-register",
        json={"new_registration": "NEW-456"},
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

async def test_vehicle_history(auth_client: AsyncClient) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()

    # Perform a transfer and a re-registration so history is non-empty
    await auth_client.post(
        f"{BASE}/{created['id']}/transfer-ownership",
        json={"new_customer_id": 7},
    )
    await auth_client.post(
        f"{BASE}/{created['id']}/re-register",
        json={"new_registration": "HIST-001"},
    )

    r = await auth_client.get(f"{BASE}/{created['id']}/history")
    assert r.status_code == 200
    history = r.json()

    assert history["vehicle"]["id"] == created["id"]
    assert len(history["ownership_history"]) == 1
    assert history["ownership_history"][0]["new_customer_id"] == 7
    assert len(history["registration_aliases"]) == 1
    assert history["registration_aliases"][0]["registration"] == "ABC-123"
    assert history["repair_orders"] == []


# ---------------------------------------------------------------------------
# Custom make / model lookup
# ---------------------------------------------------------------------------

async def test_create_vehicle_registers_custom_make_and_model(
    auth_client: AsyncClient,
) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)  # make="Toyota", model="Corolla"

    r = await auth_client.get(f"{BASE}/makes")
    assert r.status_code == 200
    assert "Toyota" in r.json()

    r = await auth_client.get(f"{BASE}/models", params={"make": "Toyota"})
    assert r.status_code == 200
    assert "Corolla" in r.json()


async def test_create_vehicle_same_make_different_case_not_duplicated(
    auth_client: AsyncClient,
) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)  # "Toyota"
    await auth_client.post(
        BASE, json={**CREATE_BODY, "registration": "ABC-124", "make": "toyota"}
    )

    r = await auth_client.get(f"{BASE}/makes")
    makes = [m for m in r.json() if m.lower() == "toyota"]
    assert len(makes) == 1


async def test_update_vehicle_make_registers_new_custom_make(
    auth_client: AsyncClient,
) -> None:
    created = (await auth_client.post(BASE, json=CREATE_BODY)).json()
    await auth_client.patch(f"{BASE}/{created['id']}", json={"make": "Skoda"})

    r = await auth_client.get(f"{BASE}/makes")
    assert "Skoda" in r.json()


async def test_delete_custom_make(auth_client: AsyncClient) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)  # "Toyota"

    r = await auth_client.delete(f"{BASE}/makes/Toyota")
    assert r.status_code == 204

    r = await auth_client.get(f"{BASE}/makes")
    assert "Toyota" not in r.json()


async def test_delete_unknown_custom_make_returns_404(auth_client: AsyncClient) -> None:
    r = await auth_client.delete(f"{BASE}/makes/Nonexistent")
    assert r.status_code == 404


async def test_delete_custom_model(auth_client: AsyncClient) -> None:
    await auth_client.post(BASE, json=CREATE_BODY)  # make="Toyota", model="Corolla"

    r = await auth_client.delete(f"{BASE}/models/Toyota/Corolla")
    assert r.status_code == 204

    r = await auth_client.get(f"{BASE}/models", params={"make": "Toyota"})
    assert "Corolla" not in r.json()
