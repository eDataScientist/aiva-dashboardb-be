from __future__ import annotations

import pytest

from app.core.security import create_access_token, decode_access_token, hash_password
from app.models.account import Account


async def _seed_account(
    db_session,
    *,
    email: str = "auth.user@example.com",
    password: str = "StrongPassword!123",
    full_name: str = "Auth User",
    role: str = "analyst",
    is_active: bool = True,
) -> Account:
    account = Account(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_login_happy_path_returns_token_and_account_context(client, db_session) -> None:
    account = await _seed_account(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "  AUTH.USER@EXAMPLE.COM ",
            "password": "StrongPassword!123",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token"]["token_type"] == "bearer"
    assert body["token"]["expires_in_seconds"] > 0
    assert body["account"]["email"] == "auth.user@example.com"
    assert body["account"]["role"] == "analyst"
    assert body["account"]["last_login_at"] is not None

    claims = decode_access_token(body["token"]["access_token"])
    assert claims.sub == str(account.id)
    assert claims.email == "auth.user@example.com"
    assert claims.role.value == "analyst"


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client, db_session) -> None:
    await _seed_account(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "auth.user@example.com",
            "password": "WrongPassword!123",
        },
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_credentials"
    assert detail["message"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_rejects_inactive_account(client, db_session) -> None:
    await _seed_account(
        db_session,
        email="inactive@example.com",
        is_active=False,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@example.com",
            "password": "StrongPassword!123",
        },
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "account_inactive"
    assert detail["message"] == "Account is inactive."


@pytest.mark.asyncio
async def test_login_payload_validation_errors(client) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid-email-format",
            "password": "StrongPassword!123",
        },
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "auth.user@example.com",
            "password": "   ",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_me_happy_path_returns_current_account(client, db_session) -> None:
    account = await _seed_account(db_session)
    token = create_access_token(
        subject=str(account.id),
        email=account.email,
        role=account.role,
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    account_payload = response.json()["account"]
    assert account_payload["id"] == str(account.id)
    assert account_payload["email"] == "auth.user@example.com"
    assert account_payload["role"] == "analyst"
    assert account_payload["is_active"] is True


@pytest.mark.asyncio
async def test_auth_me_rejects_missing_or_invalid_token(client) -> None:
    missing = await client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert missing.json()["detail"]["code"] == "authentication_required"

    invalid = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid-token"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"]["code"] == "invalid_token"
