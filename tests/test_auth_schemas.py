from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.accounts import AccountProfilePatchRequest
from app.schemas.auth import LoginRequest, TokenClaims


def test_login_request_normalizes_email() -> None:
    payload = LoginRequest(email="  USER@Example.Com  ", password="secret")
    assert payload.email == "user@example.com"


def test_login_request_rejects_blank_password() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="   ")


def test_account_profile_patch_rejects_blank_full_name() -> None:
    with pytest.raises(ValidationError):
        AccountProfilePatchRequest(full_name="   ")


def test_token_claims_require_access_type() -> None:
    with pytest.raises(ValidationError):
        TokenClaims(
            sub="11111111-1111-1111-1111-111111111111",
            email="user@example.com",
            role="analyst",
            type="refresh",
            iat=10,
            exp=20,
        )

