from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AUTH_BEARER_SCHEME
from app.core.security import TokenDecodeError, TokenExpiredError, decode_access_token
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.auth import AuthErrorCode, AuthErrorResponse, TokenClaims

_bearer_scheme = HTTPBearer(auto_error=False)


def _raise_auth_error(code: AuthErrorCode, message: str) -> HTTPException:
    payload = AuthErrorResponse(code=code, message=message).model_dump()
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=payload)


async def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> TokenClaims:
    if credentials is None:
        raise _raise_auth_error(
            AuthErrorCode.AUTHENTICATION_REQUIRED,
            "Authentication is required.",
        )

    scheme = (credentials.scheme or "").strip().lower()
    if scheme != AUTH_BEARER_SCHEME:
        raise _raise_auth_error(
            AuthErrorCode.INVALID_TOKEN,
            "Unsupported authorization scheme.",
        )

    token = (credentials.credentials or "").strip()
    if not token:
        raise _raise_auth_error(
            AuthErrorCode.INVALID_TOKEN,
            "Bearer token is missing.",
        )

    try:
        return decode_access_token(token)
    except TokenExpiredError as exc:
        raise _raise_auth_error(AuthErrorCode.INVALID_TOKEN, "Token has expired.") from exc
    except TokenDecodeError as exc:
        raise _raise_auth_error(AuthErrorCode.INVALID_TOKEN, "Token is invalid.") from exc


async def get_current_account(
    claims: TokenClaims = Depends(get_token_claims),
    db: AsyncSession = Depends(get_db),
) -> Account:
    try:
        account_id = UUID(claims.sub)
    except ValueError as exc:
        raise _raise_auth_error(
            AuthErrorCode.INVALID_TOKEN,
            "Token subject is invalid.",
        ) from exc

    account = await db.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise _raise_auth_error(
            AuthErrorCode.INVALID_TOKEN,
            "Token subject account was not found.",
        )
    if not account.is_active:
        raise _raise_auth_error(
            AuthErrorCode.ACCOUNT_INACTIVE,
            "Account is inactive.",
        )

    return account

