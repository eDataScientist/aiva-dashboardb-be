from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_settings(**overrides: str | int) -> dict[str, str | int]:
    values: dict[str, str | int] = {
        "database_url": "postgresql://dummy:dummy@localhost:5432/dummy",
        "auth_jwt_secret": "grading-config-secret-at-least-32-chars",
        "auth_jwt_algorithm": "HS256",
        "auth_access_token_expire_minutes": 60,
    }
    values.update(overrides)
    return values


def test_settings_default_to_mock_grading_provider() -> None:
    settings = Settings(**_base_settings())
    assert settings.grading_provider == "mock"
    assert settings.grading_model == "mock-grade-v1"
    assert settings.grading_request_timeout_seconds == 30
    assert settings.grading_max_retries == 2
    assert settings.grading_prompt_version == "v1"
    assert settings.grading_prompt_assets_root is None
    assert settings.grading_batch_scheduler_enabled is False
    assert settings.grading_batch_scheduler_hour_gst == 1
    assert settings.grading_batch_max_backfill_days == 31
    assert settings.grading_batch_stale_run_timeout_minutes == 180
    assert settings.grading_batch_allow_mock_provider_runs is False
    assert settings.grading_batch_timezone == "Asia/Dubai"


def test_settings_require_api_key_for_openai_compatible_provider() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                grading_provider="openai_compatible",
                grading_api_key="   ",
            )
        )


def test_settings_reject_invalid_grading_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_settings(grading_request_timeout_seconds=0))


def test_settings_reject_invalid_batch_scheduler_hour() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_settings(grading_batch_scheduler_hour_gst=24))


def test_settings_reject_invalid_batch_backfill_window() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_settings(grading_batch_max_backfill_days=0))


def test_settings_reject_invalid_stale_run_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_settings(grading_batch_stale_run_timeout_minutes=0))


def test_settings_normalize_optional_grading_fields() -> None:
    settings = Settings(
        **_base_settings(
            grading_api_key="  api-key  ",
            grading_base_url="  https://example.test/v1  ",
            grading_prompt_assets_root="  app/prompt_assets/grading  ",
        )
    )
    assert settings.grading_api_key == "api-key"
    assert settings.grading_base_url == "https://example.test/v1"
    assert settings.grading_prompt_assets_root == "app/prompt_assets/grading"


def test_settings_require_non_mock_provider_when_scheduler_enabled() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_settings(grading_batch_scheduler_enabled=True))


def test_settings_allow_mock_provider_when_explicitly_enabled_for_batch_runs() -> None:
    settings = Settings(
        **_base_settings(
            grading_batch_scheduler_enabled=True,
            grading_batch_allow_mock_provider_runs=True,
        )
    )
    assert settings.grading_batch_scheduler_enabled is True
    assert settings.grading_batch_allow_mock_provider_runs is True


def test_settings_reject_missing_prompt_pack_directory() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                grading_prompt_assets_root="tests/fixtures/does-not-exist",
                grading_prompt_version="missing-version",
            )
        )
