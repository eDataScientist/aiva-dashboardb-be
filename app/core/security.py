from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.constants import (
    AUTH_BEARER_SCHEME,
    AUTH_PASSWORD_HASH_DIGEST,
    AUTH_PASSWORD_HASH_ITERATIONS,
    AUTH_PASSWORD_HASH_SALT_BYTES,
    AUTH_PASSWORD_HASH_SCHEME,
    AUTH_REQUIRED_TOKEN_CLAIMS,
    AUTH_TOKEN_TYPE_ACCESS,
)
from app.schemas.auth import TokenClaims, TokenResponse


class TokenDecodeError(ValueError):
    """Raised when an access token is malformed or fails validation."""


class TokenExpiredError(TokenDecodeError):
    """Raised when an access token is expired."""


def hash_password(
    password: str,
    *,
    iterations: int = AUTH_PASSWORD_HASH_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    normalized = password or ""
    if not normalized.strip():
        raise ValueError("password must not be blank.")
    if iterations <= 0:
        raise ValueError("iterations must be greater than 0.")

    effective_salt = salt or secrets.token_bytes(AUTH_PASSWORD_HASH_SALT_BYTES)
    digest = _derive_password_digest(
        password=normalized,
        salt=effective_salt,
        iterations=iterations,
    )
    return (
        f"{AUTH_PASSWORD_HASH_SCHEME}${iterations}$"
        f"{_b64url_encode(effective_salt)}${_b64url_encode(digest)}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False

    try:
        scheme, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if scheme != AUTH_PASSWORD_HASH_SCHEME:
            return False

        iterations = int(iterations_text)
        salt = _b64url_decode(salt_text)
        expected_digest = _b64url_decode(digest_text)
    except (ValueError, TypeError):
        return False

    actual_digest = _derive_password_digest(
        password=password,
        salt=salt,
        iterations=iterations,
    )
    return hmac.compare_digest(expected_digest, actual_digest)


def build_access_token_response(
    *,
    subject: str,
    email: str,
    role: str,
    settings: Settings | None = None,
    expires_in_seconds: int | None = None,
) -> TokenResponse:
    effective_settings = settings or get_settings()
    ttl_seconds = (
        int(expires_in_seconds)
        if expires_in_seconds is not None
        else effective_settings.auth_access_token_expire_minutes * 60
    )
    token = create_access_token(
        subject=subject,
        email=email,
        role=role,
        settings=effective_settings,
        expires_in_seconds=ttl_seconds,
    )
    return TokenResponse(
        access_token=token,
        token_type=AUTH_BEARER_SCHEME,
        expires_in_seconds=ttl_seconds,
    )


def create_access_token(
    *,
    subject: str,
    email: str,
    role: str,
    settings: Settings | None = None,
    expires_in_seconds: int | None = None,
    issued_at: datetime | None = None,
) -> str:
    effective_settings = settings or get_settings()
    algorithm = effective_settings.auth_jwt_algorithm
    secret = effective_settings.auth_jwt_secret.encode("utf-8")

    now = issued_at or datetime.now(timezone.utc)
    issued_at_ts = int(now.timestamp())
    ttl_seconds = (
        int(expires_in_seconds)
        if expires_in_seconds is not None
        else effective_settings.auth_access_token_expire_minutes * 60
    )

    payload: dict[str, Any] = {
        "sub": subject.strip(),
        "email": email.strip().lower(),
        "role": role.strip(),
        "type": AUTH_TOKEN_TYPE_ACCESS,
        "iat": issued_at_ts,
        "exp": issued_at_ts + ttl_seconds,
    }
    if effective_settings.auth_jwt_issuer:
        payload["iss"] = effective_settings.auth_jwt_issuer
    if effective_settings.auth_jwt_audience:
        payload["aud"] = effective_settings.auth_jwt_audience

    header = {"alg": algorithm, "typ": "JWT"}
    encoded_header = _b64url_encode(_json_dumps(header))
    encoded_payload = _b64url_encode(_json_dumps(payload))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")

    signature = hmac.new(
        key=secret,
        msg=signing_input,
        digestmod=_get_hmac_digest(algorithm),
    ).digest()
    encoded_signature = _b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> TokenClaims:
    effective_settings = settings or get_settings()

    parts = token.split(".")
    if len(parts) != 3:
        raise TokenDecodeError("Invalid token structure.")
    encoded_header, encoded_payload, encoded_signature = parts

    try:
        header = json.loads(_b64url_decode(encoded_header).decode("utf-8"))
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
        signature = _b64url_decode(encoded_signature)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TokenDecodeError("Invalid token encoding.") from exc

    token_algorithm = str(header.get("alg", "")).upper()
    if token_algorithm != effective_settings.auth_jwt_algorithm:
        raise TokenDecodeError("Token algorithm is not allowed.")

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        key=effective_settings.auth_jwt_secret.encode("utf-8"),
        msg=signing_input,
        digestmod=_get_hmac_digest(token_algorithm),
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenDecodeError("Token signature is invalid.")

    missing_claims = [
        claim for claim in AUTH_REQUIRED_TOKEN_CLAIMS if claim not in payload
    ]
    if missing_claims:
        raise TokenDecodeError(
            f"Token is missing required claims: {', '.join(missing_claims)}."
        )

    try:
        claims = TokenClaims.model_validate(payload)
    except ValidationError as exc:
        raise TokenDecodeError("Token claims are invalid.") from exc

    now_ts = int((now or datetime.now(timezone.utc)).timestamp())
    if claims.exp <= now_ts:
        raise TokenExpiredError("Token has expired.")

    if (
        effective_settings.auth_jwt_issuer is not None
        and claims.iss != effective_settings.auth_jwt_issuer
    ):
        raise TokenDecodeError("Token issuer is invalid.")

    if (
        effective_settings.auth_jwt_audience is not None
        and claims.aud != effective_settings.auth_jwt_audience
    ):
        raise TokenDecodeError("Token audience is invalid.")

    return claims


def _derive_password_digest(
    *,
    password: str,
    salt: bytes,
    iterations: int,
) -> bytes:
    return hashlib.pbkdf2_hmac(
        AUTH_PASSWORD_HASH_DIGEST,
        password.encode("utf-8"),
        salt,
        iterations,
    )


def _json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64url_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode((payload + padding).encode("ascii"))


def _get_hmac_digest(algorithm: str):
    digest_map = {
        "HS256": hashlib.sha256,
        "HS384": hashlib.sha384,
        "HS512": hashlib.sha512,
    }
    digest = digest_map.get(algorithm.upper())
    if digest is None:
        raise TokenDecodeError(f"Unsupported algorithm: {algorithm}")
    return digest

