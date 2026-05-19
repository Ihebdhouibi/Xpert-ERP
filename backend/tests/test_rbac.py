"""Tests for RBAC permission dependency."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestProtectedEndpoints:
    """Ensure protected endpoints reject unauthenticated requests."""

    async def test_list_users_requires_auth(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/users")
        assert resp.status_code == 401

    async def test_create_user_requires_auth(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/users", json={})
        assert resp.status_code == 401

    async def test_list_users_with_valid_token(self, test_client: AsyncClient) -> None:
        # Login to get token
        login_resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        resp = await test_client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1
