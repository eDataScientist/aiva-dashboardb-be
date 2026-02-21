from __future__ import annotations

from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("DATABASE_URL must not be empty.")

        supported_prefixes = (
            "postgresql://",
            "postgresql+psycopg://",
            "postgresql+psycopg2://",
            "sqlite:///",
        )
        if not normalized.lower().startswith(tuple(prefix.lower() for prefix in supported_prefixes)):
            raise ValueError(
                "DATABASE_URL must start with one of: "
                + ", ".join(supported_prefixes)
            )
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(
            "Invalid application settings. Ensure DATABASE_URL is set."
        ) from exc

