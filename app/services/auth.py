from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.account import Account
from app.schemas.accounts import AccountContext, AccountRoleSchema
from app.schemas.auth import AuthErrorCode


@dataclass(slots=True)
class AuthenticationError(ValueError):
    code: AuthErrorCode
    message: str

    def __str__(self) -> str:
        return self.message


async def authenticate_account(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> Account:
    normalized_email = email.strip().lower()
    account = await session.scalar(
        select(Account)
        .where(func.lower(Account.email) == normalized_email)
        .limit(1)
    )

    if account is None or not verify_password(password, account.password_hash):
        raise AuthenticationError(
            code=AuthErrorCode.INVALID_CREDENTIALS,
            message="Invalid email or password.",
        )

    if not account.is_active:
        raise AuthenticationError(
            code=AuthErrorCode.ACCOUNT_INACTIVE,
            message="Account is inactive.",
        )

    account.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    await session.refresh(account)
    return account


def to_account_context(account: Account) -> AccountContext:
    return AccountContext(
        id=account.id,
        email=account.email,
        full_name=account.full_name,
        role=AccountRoleSchema(account.role),
        is_active=account.is_active,
        last_login_at=account.last_login_at,
    )
