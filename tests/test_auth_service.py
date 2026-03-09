from __future__ import annotations

from datetime import datetime

import pytest

from app.core.security import hash_password
from app.models.account import Account
from app.schemas.auth import AuthErrorCode
from app.services.auth import AuthenticationError, authenticate_account, to_account_context


async def _seed_account(
    db_session,
    *,
    email: str = "analyst@example.com",
    password: str = "StrongPassword!123",
    full_name: str = "Analyst User",
    role: str = "analyst",
    is_active: bool = True,
    last_login_at: datetime | None = None,
) -> Account:
    account = Account(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
        last_login_at=last_login_at,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_authenticate_account_happy_path_updates_last_login(db_session) -> None:
    account = await _seed_account(db_session)

    authenticated = await authenticate_account(
        db_session,
        email="  ANALYST@EXAMPLE.COM ",
        password="StrongPassword!123",
    )

    assert authenticated.id == account.id
    assert authenticated.last_login_at is not None


@pytest.mark.asyncio
async def test_authenticate_account_rejects_unknown_email(db_session) -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        await authenticate_account(
            db_session,
            email="missing@example.com",
            password="StrongPassword!123",
        )

    assert exc_info.value.code == AuthErrorCode.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_authenticate_account_rejects_wrong_password(db_session) -> None:
    await _seed_account(db_session)

    with pytest.raises(AuthenticationError) as exc_info:
        await authenticate_account(
            db_session,
            email="analyst@example.com",
            password="WrongPassword!123",
        )

    assert exc_info.value.code == AuthErrorCode.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_authenticate_account_rejects_inactive_account(db_session) -> None:
    await _seed_account(
        db_session,
        email="inactive@example.com",
        is_active=False,
    )

    with pytest.raises(AuthenticationError) as exc_info:
        await authenticate_account(
            db_session,
            email="inactive@example.com",
            password="StrongPassword!123",
        )

    assert exc_info.value.code == AuthErrorCode.ACCOUNT_INACTIVE


@pytest.mark.asyncio
async def test_to_account_context_maps_expected_fields(db_session) -> None:
    account = await _seed_account(db_session)
    context = to_account_context(account)

    assert context.id == account.id
    assert context.email == "analyst@example.com"
    assert context.full_name == "Analyst User"
    assert context.role.value == "analyst"
    assert context.is_active is True
