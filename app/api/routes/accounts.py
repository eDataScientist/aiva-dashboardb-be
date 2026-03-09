from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_account
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.accounts import (
    AccountMeResponse,
    AccountProfilePatchRequest,
    AccountProfilePatchResponse,
)
from app.services.accounts import AccountNotFoundError, get_account_profile, update_account_profile

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.get(
    "/me",
    response_model=AccountMeResponse,
    summary="Get authenticated account profile",
)
async def get_profile(
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountMeResponse:
    try:
        return await get_account_profile(db, current_account.id)
    except AccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")


@router.patch(
    "/me",
    response_model=AccountProfilePatchResponse,
    summary="Update authenticated account profile",
)
async def patch_profile(
    patch: AccountProfilePatchRequest,
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountProfilePatchResponse:
    try:
        return await update_account_profile(db, current_account.id, patch)
    except AccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
