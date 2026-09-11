"""Integration tests for auth HTTP endpoints."""
from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

from app.modules.notification.adapter import DeliveryResult, EmailAdapter


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

    async def test_request_reset_sends_email_to_correct_recipient(
        self, test_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: dict = {}

        async def fake_send(self, recipient, channel, subject, body, attachments=None):
            sent["recipient"] = recipient
            sent["subject"] = subject
            sent["body"] = body
            return DeliveryResult(success=True)

        monkeypatch.setattr(EmailAdapter, "send", fake_send)

        resp = await test_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@test.com"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 202
        assert sent["recipient"] == "admin@test.com"
        assert "réinitialisation" in sent["subject"].lower()
        assert "reset-password" in sent["body"]

    async def test_request_reset_unknown_email_sends_no_email(
        self, test_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"count": 0}

        async def fake_send(self, recipient, channel, subject, body, attachments=None):
            called["count"] += 1
            return DeliveryResult(success=True)

        monkeypatch.setattr(EmailAdapter, "send", fake_send)

        resp = await test_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "unknown@test.com"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 202
        assert called["count"] == 0

    async def test_request_reset_email_failure_still_returns_202(
        self, test_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An SMTP outage must never surface as a distinguishable response —
        that would leak whether the email exists and/or break UX on outage."""

        async def failing_send(self, recipient, channel, subject, body, attachments=None):
            return DeliveryResult(success=False, error="SMTPConnectError")

        monkeypatch.setattr(EmailAdapter, "send", failing_send)

        resp = await test_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@test.com"},
            headers={"X-Garage-ID": "1"},
        )
        assert resp.status_code == 202


@pytest.mark.asyncio
class TestPasswordResetConfirmEndpoint:
    async def test_confirm_missing_header_returns_400(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "whatever", "new_password": "NewPassword123"},
        )
        assert resp.status_code == 400

    async def test_confirm_invalid_token_returns_400(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "not-a-real-token", "new_password": "NewPassword123"},
            headers={"X-Reset-Email": "admin@test.com"},
        )
        assert resp.status_code == 400

    async def test_confirm_weak_password_returns_422(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "whatever", "new_password": "short"},
            headers={"X-Reset-Email": "admin@test.com"},
        )
        assert resp.status_code == 422

    async def test_full_reset_round_trip_via_http(
        self, test_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulates the real user journey: request link -> extract token from
        the email that would have been sent -> confirm -> log in with the new
        password. This is the flow the login page's 'Mot de passe oublié ?'
        link drives end to end."""
        captured: dict = {}

        async def fake_send(self, recipient, channel, subject, body, attachments=None):
            captured["body"] = body
            return DeliveryResult(success=True)

        monkeypatch.setattr(EmailAdapter, "send", fake_send)

        req_resp = await test_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@test.com"},
            headers={"X-Garage-ID": "1"},
        )
        assert req_resp.status_code == 202

        match = re.search(r"token=([^&\"']+)", captured["body"])
        assert match, "reset link with a token must be present in the email body"
        raw_token = match.group(1)

        confirm_resp = await test_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "BrandNewPass123"},
            headers={"X-Reset-Email": "admin@test.com"},
        )
        assert confirm_resp.status_code == 200

        # Old password must no longer work.
        old_login = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Test1234!"},
            headers={"X-Garage-ID": "1"},
        )
        assert old_login.status_code == 401

        # New password logs in successfully.
        new_login = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "BrandNewPass123"},
            headers={"X-Garage-ID": "1"},
        )
        assert new_login.status_code == 200

        # The same reset link cannot be replayed.
        replay_resp = await test_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "YetAnotherPass789"},
            headers={"X-Reset-Email": "admin@test.com"},
        )
        assert replay_resp.status_code == 400


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_ok(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
