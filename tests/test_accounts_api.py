from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.account import Account


def _make_token(account: Account) -> str:
    return create_access_token(
        subject=str(account.id),
        email=account.email,
        role=account.role,
    )


def _auth_headers(account: Account) -> dict:
    return {"Authorization": f"Bearer {_make_token(account)}"}


@pytest_asyncio.fixture()
async def active_account(db_session):
    account = Account(
        id=uuid.uuid4(),
        email="profile.user@example.com",
        password_hash=hash_password("test-pass-word-123"),
        full_name="Profile User",
        role="analyst",
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest_asyncio.fixture()
async def inactive_account(db_session):
    account = Account(
        id=uuid.uuid4(),
        email="inactive.user@example.com",
        password_hash=hash_password("test-pass-word-123"),
        full_name="Inactive User",
        role="analyst",
        is_active=False,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_get_profile_returns_account_context(
    client: AsyncClient, active_account: Account
):
    response = await client.get(
        "/api/v1/accounts/me",
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 200
    data = response.json()
    assert "account" in data
    assert data["account"]["email"] == "profile.user@example.com"
    assert data["account"]["full_name"] == "Profile User"
    assert data["account"]["role"] == "analyst"
    assert data["account"]["is_active"] is True


@pytest.mark.asyncio
async def test_get_profile_without_auth_returns_401(client: AsyncClient):
    response = await client.get("/api/v1/accounts/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_with_invalid_token_returns_401(client: AsyncClient):
    response = await client.get(
        "/api/v1/accounts/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_profile_updates_full_name(
    client: AsyncClient, active_account: Account
):
    response = await client.patch(
        "/api/v1/accounts/me",
        json={"full_name": "Updated Name"},
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["account"]["full_name"] == "Updated Name"
    assert data["account"]["email"] == "profile.user@example.com"


@pytest.mark.asyncio
async def test_patch_profile_without_auth_returns_401(client: AsyncClient):
    response = await client.patch(
        "/api/v1/accounts/me",
        json={"full_name": "No Auth"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_profile_with_blank_full_name_returns_422(
    client: AsyncClient, active_account: Account
):
    response = await client.patch(
        "/api/v1/accounts/me",
        json={"full_name": "   "},
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_missing_full_name_returns_422(
    client: AsyncClient, active_account: Account
):
    response = await client.patch(
        "/api/v1/accounts/me",
        json={},
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_with_invalid_token_returns_401(client: AsyncClient):
    response = await client.patch(
        "/api/v1/accounts/me",
        json={"full_name": "Valid Name"},
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_profile_with_oversized_full_name_returns_422(
    client: AsyncClient, active_account: Account
):
    response = await client.patch(
        "/api/v1/accounts/me",
        json={"full_name": "A" * 151},
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_profile_with_inactive_account_token_returns_401(
    client: AsyncClient, inactive_account: Account
):
    response = await client.get(
        "/api/v1/accounts/me",
        headers=_auth_headers(inactive_account),
    )
    assert response.status_code == 401
