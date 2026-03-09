from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.accounts import AccountContext, AccountRoleSchema
from app.schemas.analytics import SchemaModel


class AuthErrorCode(str, Enum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    INVALID_TOKEN = "invalid_token"
    ACCOUNT_INACTIVE = "account_inactive"


class AuthErrorResponse(SchemaModel):
    code: AuthErrorCode = Field(description="Stable auth error code.")
    message: str = Field(
        min_length=1,
        description="Human-readable auth error summary.",
    )


class LoginRequest(SchemaModel):
    email: str = Field(
        ...,
        min_length=3,
        max_length=320,
        description="Account email used to authenticate.",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Raw password input used for verification.",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email must not be blank.")
        if "@" not in normalized:
            raise ValueError("email must contain '@'.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("password must not be blank.")
        return value


class TokenResponse(SchemaModel):
    access_token: str = Field(
        ...,
        min_length=1,
        description="Signed JWT access token.",
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Bearer token type.",
    )
    expires_in_seconds: int = Field(
        ...,
        gt=0,
        description="Access token time-to-live in seconds.",
    )


class LoginResponse(SchemaModel):
    token: TokenResponse = Field(description="Issued access token payload.")
    account: AccountContext = Field(
        description="Authenticated account context returned after login.",
    )


class AuthMeResponse(SchemaModel):
    account: AccountContext = Field(
        description="Current account context resolved from bearer token.",
    )


class TokenClaims(SchemaModel):
    sub: str = Field(description="Account id as string UUID.")
    email: str = Field(description="Normalized account email.")
    role: AccountRoleSchema = Field(description="Account role claim.")
    type: Literal["access"] = Field(description="Token type claim.")
    iat: int = Field(ge=0, description="Issued-at timestamp.")
    exp: int = Field(ge=0, description="Expiration timestamp.")
    iss: str | None = Field(default=None, description="Optional issuer claim.")
    aud: str | None = Field(default=None, description="Optional audience claim.")

    @field_validator("sub", "email")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("claim value must not be blank.")
        return normalized

