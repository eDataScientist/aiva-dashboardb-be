from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import get_settings
from app.core.security import (
    TokenDecodeError,
    TokenExpiredError,
    build_access_token_response,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")
    monkeypatch.setenv("AUTH_JWT_SECRET", "security-test-secret-at-least-32-characters")
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.delenv("AUTH_JWT_ISSUER", raising=False)
    monkeypatch.delenv("AUTH_JWT_AUDIENCE", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_hash_and_verify_password_round_trip() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", password_hash) is True


def test_verify_password_returns_false_for_invalid_password() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", password_hash) is False


def test_create_and_decode_access_token_round_trip() -> None:
    token = create_access_token(
        subject="11111111-1111-1111-1111-111111111111",
        email="user@example.com",
        role="analyst",
    )
    claims = decode_access_token(token)
    assert claims.sub == "11111111-1111-1111-1111-111111111111"
    assert claims.email == "user@example.com"
    assert claims.role.value == "analyst"
    assert claims.type == "access"


def test_decode_access_token_rejects_invalid_signature() -> None:
    token = create_access_token(
        subject="11111111-1111-1111-1111-111111111111",
        email="user@example.com",
        role="analyst",
    )
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(TokenDecodeError):
        decode_access_token(tampered)


def test_decode_access_token_rejects_expired_token() -> None:
    token = create_access_token(
        subject="11111111-1111-1111-1111-111111111111",
        email="user@example.com",
        role="analyst",
        issued_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        expires_in_seconds=60,
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_build_access_token_response_shape() -> None:
    response = build_access_token_response(
        subject="11111111-1111-1111-1111-111111111111",
        email="user@example.com",
        role="analyst",
    )
    assert response.token_type == "bearer"
    assert response.expires_in_seconds == 3600
    assert response.access_token

