"""Unit tests for auth service — hashing, JWT, token lifecycle."""
from __future__ import annotations

import pytest
from jose import JWTError

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
