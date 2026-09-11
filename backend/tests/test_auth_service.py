"""Unit tests for auth service — hashing, JWT, token lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jwt.exceptions import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import service
from app.modules.auth.models import AppUser
from app.modules.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify_success(self) -> None:
        hashed = hash_password("MySecret1!")
        assert verify_password("MySecret1!", hashed)

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("MySecret1!")
        assert not verify_password("wrong", hashed)

    def test_verify_empty_password(self) -> None:
        hashed = hash_password("MySecret1!")
        assert not verify_password("", hashed)

    def test_needs_rehash_returns_bool(self) -> None:
        hashed = hash_password("MySecret1!")
        result = needs_rehash(hashed)
        assert isinstance(result, bool)


class TestJWT:
    def test_access_token_round_trip(self) -> None:
        token, expires_in = create_access_token(
            subject="test-uuid",
            garage_id=1,
            roles=["admin"],
            permissions=["users.read"],
        )
        assert isinstance(token, str)
        assert expires_in > 0

        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == "test-uuid"
        assert payload["gid"] == 1
        assert "users.read" in payload["perms"]

    def test_refresh_token_round_trip(self) -> None:
        token, jti = create_refresh_token(subject="test-uuid")
        assert isinstance(jti, str) and len(jti) > 0

        payload = decode_token(token, expected_type="refresh")
        assert payload["sub"] == "test-uuid"
        assert payload["jti"] == jti

    def test_wrong_token_type_raises(self) -> None:
        access_token, _ = create_access_token("s", 1, [], [])
        with pytest.raises(JWTError):
            decode_token(access_token, expected_type="refresh")

    def test_tampered_token_raises(self) -> None:
        token, _ = create_access_token("s", 1, [], [])
        tampered = token[:-4] + "xxxx"
        with pytest.raises(JWTError):
            decode_token(tampered)


@pytest.mark.asyncio
class TestPasswordReset:
    """End-to-end coverage of the reset-token lifecycle at the service layer,
    independent of any real SMTP provider (EmailAdapter is the router's job)."""

    async def test_unknown_email_returns_no_token(self, seeded_db: AsyncSession) -> None:
        raw_token = await service.request_password_reset(
            db=seeded_db, garage_id=1, email="nobody@test.com"
        )
        assert raw_token is None

    async def test_request_then_confirm_round_trip(self, seeded_db: AsyncSession) -> None:
        raw_token = await service.request_password_reset(
            db=seeded_db, garage_id=1, email="admin@test.com"
        )
        assert raw_token is not None

        await service.confirm_password_reset(
            db=seeded_db,
            garage_id=1,
            email="admin@test.com",
            raw_token=raw_token,
            new_password="NewPassword123",
        )

        result = await seeded_db.execute(
            select(AppUser).where(AppUser.email == "admin@test.com")
        )
        user = result.scalar_one()
        assert service.verify_password("NewPassword123", user.password_hash)
        assert not service.verify_password("Test1234!", user.password_hash)

    async def test_confirm_with_wrong_token_raises(self, seeded_db: AsyncSession) -> None:
        await service.request_password_reset(
            db=seeded_db, garage_id=1, email="admin@test.com"
        )
        with pytest.raises(ValueError, match="Invalid reset token"):
            await service.confirm_password_reset(
                db=seeded_db,
                garage_id=1,
                email="admin@test.com",
                raw_token="not-the-real-token",
                new_password="NewPassword123",
            )

    async def test_confirm_with_expired_token_raises(self, seeded_db: AsyncSession) -> None:
        raw_token = await service.request_password_reset(
            db=seeded_db, garage_id=1, email="admin@test.com"
        )
        # Force the stored expiry into the past.
        result = await seeded_db.execute(
            select(AppUser).where(AppUser.email == "admin@test.com")
        )
        user = result.scalar_one()
        user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await seeded_db.commit()

        with pytest.raises(ValueError, match="expired"):
            await service.confirm_password_reset(
                db=seeded_db,
                garage_id=1,
                email="admin@test.com",
                raw_token=raw_token,
                new_password="NewPassword123",
            )

    async def test_reset_token_is_single_use(self, seeded_db: AsyncSession) -> None:
        raw_token = await service.request_password_reset(
            db=seeded_db, garage_id=1, email="admin@test.com"
        )
        await service.confirm_password_reset(
            db=seeded_db,
            garage_id=1,
            email="admin@test.com",
            raw_token=raw_token,
            new_password="NewPassword123",
        )
        # Replaying the same (now-consumed) token must fail, not succeed again.
        with pytest.raises(ValueError, match="No pending password reset"):
            await service.confirm_password_reset(
                db=seeded_db,
                garage_id=1,
                email="admin@test.com",
                raw_token=raw_token,
                new_password="AnotherPassword456",
            )
