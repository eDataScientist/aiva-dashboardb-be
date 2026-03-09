from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.accounts import (
    AccountContext,
    AccountMeResponse,
    AccountProfilePatchRequest,
    AccountProfilePatchResponse,
    AccountRoleSchema,
)


class AccountNotFoundError(ValueError):
    """Raised when an account cannot be found by the given identifier."""


def _build_account_context(account: Account) -> AccountContext:
    return AccountContext(
        id=account.id,
        email=account.email,
        full_name=account.full_name,
        role=AccountRoleSchema(account.role),
        is_active=account.is_active,
        last_login_at=account.last_login_at,
    )


async def get_account_profile(
    db: AsyncSession,
    account_id: UUID,
) -> AccountMeResponse:
    account = await db.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise AccountNotFoundError(f"Account {account_id} not found.")
    return AccountMeResponse(account=_build_account_context(account))


async def update_account_profile(
    db: AsyncSession,
    account_id: UUID,
    patch: AccountProfilePatchRequest,
) -> AccountProfilePatchResponse:
    account = await db.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise AccountNotFoundError(f"Account {account_id} not found.")

    account.full_name = patch.full_name
    account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    await db.refresh(account)
    return AccountProfilePatchResponse(account=_build_account_context(account))
