"""Integration tests for auth HTTP endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestLoginEndpoint:
    async def test_login_success(self, test_client: AsyncClient) -> None:
        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "admin@test.com"
        assert "users.read" in data["user"]["permissions"]

    async def test_login_wrong_password(self, test_client: AsyncClient) -> None:
        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "wrongpass"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email(self, test_client: AsyncClient) -> None:
        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 401

    async def test_login_invalid_email_format(self, test_client: AsyncClient) -> None:
        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "Test1234!"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogoutEndpoint:
    async def test_logout_returns_204(self, test_client: AsyncClient) -> None:
        # Login first
        login_resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = await test_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 204

    async def test_logout_with_invalid_token_is_silent(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "invalid.token.value"},
        )
        # Logout is always silent — no error on invalid token
        assert resp.status_code == 204


@pytest.mark.asyncio
class TestPasswordResetEndpoint:
    async def test_request_reset_always_202(self, test_client: AsyncClient) -> None:
        resp = await test_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@test.com"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 202

    async def test_request_reset_unknown_email_still_202(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "unknown@test.com"},
            headers={"X-Garage-ID": "1"},
        )
        # Must not reveal whether the email exists
        assert resp.status_code == 202


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_ok(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
