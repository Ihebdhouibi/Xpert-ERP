"""Integration tests for time entry and comment endpoints (Issue #21)."""
from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app
from app.modules.auth.models import Permission, Role, RolePermission

RO_PERMISSIONS = (
    "repair_order.read",
    "repair_order.create",
    "repair_order.update",
    "repair_order.delete",
    "repair_order.transition",
)


@pytest_asyncio.fixture
async def te_seeded_db(seeded_db: AsyncSession) -> AsyncSession:
    role_row = (await seeded_db.execute(
        select(Role).where(Role.code == "admin")
    )).scalar_one()

    for code in RO_PERMISSIONS:
        perm = Permission(
            code=code,
            resource=code.split(".")[0],
            action=".".join(code.split(".")[1:]),
            description="",
        )
        seeded_db.add(perm)
    await seeded_db.flush()

    for code in RO_PERMISSIONS:
        perm_row = (await seeded_db.execute(
            select(Permission).where(Permission.code == code)
        )).scalar_one()
        seeded_db.add(RolePermission(role_id=role_row.id, permission_id=perm_row.id))
    await seeded_db.commit()
    return seeded_db


@pytest_asyncio.fixture
async def te_client(
    te_seeded_db: AsyncSession, mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield te_seeded_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Test1234!"},
        headers={"X-Garage-ID": "1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Garage-ID": "1"}


async def _create_ro(client: AsyncClient, token: str) -> str:
    """Create a repair order and return its public_id (UUID string)."""
    resp = await client.post(
        "/api/v1/repair-orders",
        json={"customer_id": 1, "description": "Test RO for time entries"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Time Entry tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTimeEntryStart:
    async def test_start_creates_open_entry(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["ended_at"] is None
        assert body["duration_minutes"] is None

    async def test_start_with_notes(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={"notes": "Started diagnosis"},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["notes"] == "Started diagnosis"

    async def test_start_twice_returns_409(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )
        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    async def test_start_requires_auth(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
        )
        assert resp.status_code == 401

    async def test_start_invalid_ro_returns_404(self, te_client: AsyncClient):
        token = await _login(te_client)
        resp = await te_client.post(
            "/api/v1/repair-orders/00000000-0000-0000-0000-000000000000/time-entries/start",
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTimeEntryStop:
    async def test_stop_closes_entry(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )
        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/stop",
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ended_at"] is not None
        assert body["duration_minutes"] is not None
        assert body["duration_minutes"] >= 1

    async def test_stop_without_open_entry_returns_404(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/stop",
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    async def test_stop_with_notes(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )
        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/stop",
            json={"notes": "Finished diagnosis"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Finished diagnosis"


@pytest.mark.asyncio
class TestTimeEntryList:
    async def test_list_empty(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.get(
            f"/api/v1/repair-orders/{public_id}/time-entries",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_includes_open_and_closed(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )
        await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/stop",
            json={},
            headers=_auth(token),
        )
        await te_client.post(
            f"/api/v1/repair-orders/{public_id}/time-entries/start",
            json={},
            headers=_auth(token),
        )

        resp = await te_client.get(
            f"/api/v1/repair-orders/{public_id}/time-entries",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Comment tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCommentCreate:
    async def test_create_comment(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/comments",
            json={"body": "Customer called, parts ordered."},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["body"] == "Customer called, parts ordered."

    async def test_create_empty_body_rejected(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/comments",
            json={"body": ""},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_create_requires_auth(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/comments",
            json={"body": "Test"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestCommentList:
    async def test_list_empty(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.get(
            f"/api/v1/repair-orders/{public_id}/comments",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_returns_comments(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        for i in range(3):
            await te_client.post(
                f"/api/v1/repair-orders/{public_id}/comments",
                json={"body": f"Comment {i}"},
                headers=_auth(token),
            )

        resp = await te_client.get(
            f"/api/v1/repair-orders/{public_id}/comments",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3


@pytest.mark.asyncio
class TestCommentUpdate:
    async def test_update_own_comment(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        create_resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/comments",
            json={"body": "Original body"},
            headers=_auth(token),
        )
        comment_id = create_resp.json()["id"]

        resp = await te_client.put(
            f"/api/v1/repair-orders/{public_id}/comments/{comment_id}",
            json={"body": "Updated body"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["body"] == "Updated body"

    async def test_update_nonexistent_returns_404(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.put(
            f"/api/v1/repair-orders/{public_id}/comments/99999",
            json={"body": "Updated body"},
            headers=_auth(token),
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestCommentDelete:
    async def test_delete_own_comment(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        create_resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/comments",
            json={"body": "To be deleted"},
            headers=_auth(token),
        )
        comment_id = create_resp.json()["id"]

        resp = await te_client.delete(
            f"/api/v1/repair-orders/{public_id}/comments/{comment_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 204

    async def test_delete_hides_comment_from_list(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        create_resp = await te_client.post(
            f"/api/v1/repair-orders/{public_id}/comments",
            json={"body": "Will disappear"},
            headers=_auth(token),
        )
        comment_id = create_resp.json()["id"]

        await te_client.delete(
            f"/api/v1/repair-orders/{public_id}/comments/{comment_id}",
            headers=_auth(token),
        )

        resp = await te_client.get(
            f"/api/v1/repair-orders/{public_id}/comments",
            headers=_auth(token),
        )
        assert resp.json()["total"] == 0

    async def test_delete_nonexistent_returns_404(self, te_client: AsyncClient):
        token = await _login(te_client)
        public_id = await _create_ro(te_client, token)

        resp = await te_client.delete(
            f"/api/v1/repair-orders/{public_id}/comments/99999",
            headers=_auth(token),
        )
        assert resp.status_code == 404
