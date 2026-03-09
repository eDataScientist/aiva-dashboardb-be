from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.analytics import SchemaModel


class AccountRoleSchema(str, Enum):
    SUPER_ADMIN = "super_admin"
    COMPANY_ADMIN = "company_admin"
    ANALYST = "analyst"


class AccountContext(SchemaModel):
    id: UUID = Field(description="Unique account identifier.")
    email: str = Field(description="Normalized account email address.")
    full_name: str = Field(description="Account display name.")
    role: AccountRoleSchema = Field(description="Account role code.")
    is_active: bool = Field(description="Whether the account is active.")
    last_login_at: datetime | None = Field(
        default=None,
        description="Timestamp of most recent successful login.",
    )


class AccountMeResponse(SchemaModel):
    account: AccountContext = Field(
        description="Authenticated account profile context.",
    )


class AccountProfilePatchRequest(SchemaModel):
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Updated full name for the authenticated account.",
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("full_name must not be blank.")
        return normalized


class AccountProfilePatchResponse(SchemaModel):
    account: AccountContext = Field(
        description="Updated authenticated account profile context.",
    )

