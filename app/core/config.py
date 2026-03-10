from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    GRADING_DEFAULT_MODEL,
    GRADING_DEFAULT_PROMPT_VERSION,
    GRADING_PROMPT_DOMAIN_ORDER,
    GRADING_PROMPT_DOMAIN_SYSTEM_PROMPT_KEYS,
    GRADING_PROMPT_DOMAIN_TO_TEMPLATE_FILE,
    GRADING_PROMPT_PACK_BASE_DIR,
    GRADING_PROMPT_REQUIRED_FILES,
    GRADING_PROMPT_SYSTEM_PROMPT_FILE,
    GRADING_PROVIDER_OPENAI_COMPATIBLE,
    GRADING_SUPPORTED_PROVIDERS,
)

_SUPPORTED_DATABASE_PREFIXES = (
    "postgresql://",
    "postgresql+psycopg://",
    "postgresql+psycopg2://",
    "sqlite:///",
)

_SUPPORTED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}
_PROMPT_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AIVA Dashboard Backend"
    app_version: str = "0.1.0"
    database_url: str = Field(
        ...,
        description="SQLAlchemy database URL for runtime connections.",
    )
    auth_jwt_secret: str = Field(
        ...,
        description="Symmetric secret used to sign and verify JWT access tokens.",
    )
    auth_jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )
    auth_access_token_expire_minutes: int = Field(
        default=60,
        description="Access token TTL in minutes.",
    )
    auth_jwt_issuer: str | None = Field(
        default=None,
        description="Optional JWT issuer claim value.",
    )
    auth_jwt_audience: str | None = Field(
        default=None,
        description="Optional JWT audience claim value.",
    )
    grading_provider: str = Field(
        default="mock",
        description="Grading provider implementation to use at runtime.",
    )
    grading_model: str = Field(
        default=GRADING_DEFAULT_MODEL,
        description="Provider-specific grading model identifier.",
    )
    grading_request_timeout_seconds: int = Field(
        default=30,
        description="Timeout budget for a single grading provider request.",
    )
    grading_max_retries: int = Field(
        default=2,
        description="Maximum retry attempts for transient grading provider failures.",
    )
    grading_prompt_version: str = Field(
        default=GRADING_DEFAULT_PROMPT_VERSION,
        description="Prompt contract version used by the grading pipeline.",
    )
    grading_prompt_assets_root: str | None = Field(
        default=None,
        description=(
            "Optional base directory override containing versioned grading prompt-pack "
            "assets."
        ),
    )
    grading_api_key: str | None = Field(
        default=None,
        description="Optional API key used by external grading providers.",
    )
    grading_base_url: str | None = Field(
        default=None,
        description="Optional base URL override for OpenAI-compatible grading providers.",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("DATABASE_URL must not be empty.")

        if not normalized.lower().startswith(
            tuple(prefix.lower() for prefix in _SUPPORTED_DATABASE_PREFIXES)
        ):
            raise ValueError(
                "DATABASE_URL must start with one of: "
                + ", ".join(_SUPPORTED_DATABASE_PREFIXES)
            )
        return normalized

    @field_validator("auth_jwt_secret")
    @classmethod
    def validate_auth_jwt_secret(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 32:
            raise ValueError("AUTH_JWT_SECRET must be at least 32 characters long.")
        return normalized

    @field_validator("auth_jwt_algorithm")
    @classmethod
    def validate_auth_jwt_algorithm(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in _SUPPORTED_JWT_ALGORITHMS:
            raise ValueError(
                "AUTH_JWT_ALGORITHM must be one of: "
                + ", ".join(sorted(_SUPPORTED_JWT_ALGORITHMS))
            )
        return normalized

    @field_validator("auth_access_token_expire_minutes")
    @classmethod
    def validate_auth_access_token_expire_minutes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0.")
        if value > 24 * 60:
            raise ValueError(
                "AUTH_ACCESS_TOKEN_EXPIRE_MINUTES must be less than or equal to 1440."
            )
        return value

    @field_validator("auth_jwt_issuer", "auth_jwt_audience")
    @classmethod
    def normalize_optional_claim_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("grading_provider")
    @classmethod
    def validate_grading_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in GRADING_SUPPORTED_PROVIDERS:
            raise ValueError(
                "GRADING_PROVIDER must be one of: "
                + ", ".join(GRADING_SUPPORTED_PROVIDERS)
            )
        return normalized

    @field_validator("grading_model", "grading_prompt_version")
    @classmethod
    def validate_required_grading_strings(cls, value: str, info) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name.upper()} must not be empty.")
        return normalized

    @field_validator("grading_prompt_assets_root")
    @classmethod
    def normalize_grading_prompt_assets_root(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("grading_request_timeout_seconds")
    @classmethod
    def validate_grading_request_timeout_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(
                "GRADING_REQUEST_TIMEOUT_SECONDS must be greater than 0."
            )
        if value > 300:
            raise ValueError(
                "GRADING_REQUEST_TIMEOUT_SECONDS must be less than or equal to 300."
            )
        return value

    @field_validator("grading_max_retries")
    @classmethod
    def validate_grading_max_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("GRADING_MAX_RETRIES must be greater than or equal to 0.")
        if value > 5:
            raise ValueError("GRADING_MAX_RETRIES must be less than or equal to 5.")
        return value

    @field_validator("grading_api_key", "grading_base_url")
    @classmethod
    def normalize_optional_grading_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_grading_provider_requirements(self) -> "Settings":
        if (
            self.grading_provider == GRADING_PROVIDER_OPENAI_COMPATIBLE
            and self.grading_api_key is None
        ):
            raise ValueError(
                "GRADING_API_KEY is required when GRADING_PROVIDER is "
                "'openai_compatible'."
            )
        _validate_prompt_pack_assets(
            root_dir=self.resolved_grading_prompt_assets_dir,
            version=self.grading_prompt_version,
        )
        return self

    @property
    def resolved_grading_prompt_assets_base_dir(self) -> Path:
        if self.grading_prompt_assets_root is None:
            return _project_root() / GRADING_PROMPT_PACK_BASE_DIR

        configured_root = Path(self.grading_prompt_assets_root)
        if not configured_root.is_absolute():
            configured_root = _project_root() / configured_root
        return configured_root

    @property
    def resolved_grading_prompt_assets_dir(self) -> Path:
        return self.resolved_grading_prompt_assets_base_dir / self.grading_prompt_version


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(
            "Invalid application settings. Ensure DATABASE_URL, AUTH_JWT_SECRET, "
            "AUTH_JWT_ALGORITHM, AUTH_ACCESS_TOKEN_EXPIRE_MINUTES, and GRADING_* "
            "settings are valid."
        ) from exc


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validate_prompt_pack_assets(*, root_dir: Path, version: str) -> None:
    if not root_dir.exists() or not root_dir.is_dir():
        raise ValueError(
            "GRADING_PROMPT_VERSION points to a missing prompt-pack directory: "
            f"{root_dir}"
        )

    missing_files = [
        file_name for file_name in GRADING_PROMPT_REQUIRED_FILES if not (root_dir / file_name).is_file()
    ]
    if missing_files:
        raise ValueError(
            "Prompt pack is missing required files for version "
            f"'{version}': {', '.join(missing_files)}"
        )

    system_prompt_text = (root_dir / GRADING_PROMPT_SYSTEM_PROMPT_FILE).read_text(
        encoding="utf-8"
    )
    system_prompt_placeholders = _extract_prompt_placeholders(system_prompt_text)
    if system_prompt_placeholders:
        raise ValueError(
            "system_prompt.md must not declare template placeholders. Found: "
            + ", ".join(sorted(system_prompt_placeholders))
        )

    for prompt_key in GRADING_PROMPT_DOMAIN_ORDER:
        file_name = GRADING_PROMPT_DOMAIN_TO_TEMPLATE_FILE[prompt_key]
        template_text = (root_dir / file_name).read_text(encoding="utf-8")
        placeholders = _extract_prompt_placeholders(template_text)

        if "conversation" not in placeholders:
            raise ValueError(
                f"{file_name} must contain the {{conversation}} placeholder."
            )

        requires_system_prompt = prompt_key in GRADING_PROMPT_DOMAIN_SYSTEM_PROMPT_KEYS
        if requires_system_prompt and "system_prompt" not in placeholders:
            raise ValueError(
                f"{file_name} must contain the {{system_prompt}} placeholder."
            )
        if not requires_system_prompt and "system_prompt" in placeholders:
            raise ValueError(
                f"{file_name} must not contain the {{system_prompt}} placeholder."
            )

        allowed_placeholders = {"conversation"}
        if requires_system_prompt:
            allowed_placeholders.add("system_prompt")
        unexpected_placeholders = placeholders - allowed_placeholders
        if unexpected_placeholders:
            raise ValueError(
                f"{file_name} contains unsupported placeholders: "
                + ", ".join(sorted(unexpected_placeholders))
            )


def _extract_prompt_placeholders(template_text: str) -> set[str]:
    return {match.group(1).strip() for match in _PROMPT_PLACEHOLDER_PATTERN.finditer(template_text)}
