from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account
from app.core.security import build_access_token_response
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.auth import (
    AuthErrorCode,
    AuthErrorResponse,
    AuthMeResponse,
    LoginRequest,
    LoginResponse,
)
from app.services.auth import AuthenticationError, authenticate_account, to_account_context

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _raise_auth_error(code: AuthErrorCode, message: str) -> HTTPException:
    payload = AuthErrorResponse(code=code, message=message).model_dump()
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=payload)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate account credentials and issue access token",
    responses={
        401: {
            "description": "Invalid credentials or inactive account.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "invalid_credentials",
                            "message": "Invalid email or password.",
                        }
                    }
                }
            },
        }
    },
)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    try:
        account = await authenticate_account(
            db,
            email=payload.email,
            password=payload.password,
        )
    except AuthenticationError as exc:
        raise _raise_auth_error(exc.code, str(exc)) from exc

    token = build_access_token_response(
        subject=str(account.id),
        email=account.email,
        role=account.role,
    )
    return LoginResponse(
        token=token,
        account=to_account_context(account),
    )


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Return current authenticated account context",
    responses={
        401: {
            "description": "Authentication is required or bearer token is invalid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "authentication_required",
                            "message": "Authentication is required.",
                        }
                    }
                }
            },
        }
    },
)
async def get_auth_me(
    current_account: Annotated[Account, Depends(get_current_account)],
) -> AuthMeResponse:
    return AuthMeResponse(account=to_account_context(current_account))
