from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.constants import (
    DASHBOARD_ATTENTION_SIGNAL_THRESHOLDS,
    DASHBOARD_DEFAULT_WINDOW_DAYS,
    DASHBOARD_DEFAULT_WORST_PERFORMERS_LIMIT,
    DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS,
    DASHBOARD_HEATMAP_SCORE_BUCKETS,
    DASHBOARD_MAX_WINDOW_DAYS,
    DASHBOARD_MAX_WORST_PERFORMERS_LIMIT,
    DASHBOARD_STORY_CARD_SEVERITY_THRESHOLDS,
    GRADING_METRICS_OUTCOME_RATE_KEYS,
    GRADING_METRICS_SCORE_KEYS,
    GRADING_RUN_SUCCESSFUL_STATUSES,
    MONITORING_ALLOWED_SORT_DIRECTIONS,
    MONITORING_ALLOWED_SORT_FIELDS,
    INTENT_CATEGORIES,
    INTENT_CODE_TO_CATEGORY,
    INTENT_CODES,
)
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
    assert settings.grading_metrics_default_window_days == 30
    assert settings.grading_metrics_max_window_days == 366
    assert settings.dashboard_default_window_days == DASHBOARD_DEFAULT_WINDOW_DAYS
    assert settings.dashboard_max_window_days == DASHBOARD_MAX_WINDOW_DAYS
    assert (
        settings.dashboard_default_worst_performers_limit
        == DASHBOARD_DEFAULT_WORST_PERFORMERS_LIMIT
    )
    assert (
        settings.dashboard_max_worst_performers_limit
        == DASHBOARD_MAX_WORST_PERFORMERS_LIMIT
    )
    assert settings.monitoring_default_window_days == 1
    assert settings.monitoring_max_window_days == 31
    assert settings.monitoring_default_page_size == 50
    assert settings.monitoring_max_page_size == 200
    assert settings.monitoring_default_recent_history_limit == 30
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


def test_settings_reject_metrics_default_window_larger_than_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                grading_metrics_default_window_days=31,
                grading_metrics_max_window_days=30,
            )
        )


def test_settings_reject_dashboard_default_window_larger_than_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                dashboard_default_window_days=32,
                dashboard_max_window_days=31,
            )
        )


def test_settings_reject_dashboard_max_window_above_phase7_cap() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                dashboard_max_window_days=DASHBOARD_MAX_WINDOW_DAYS + 1,
            )
        )


def test_settings_reject_monitoring_default_window_larger_than_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                monitoring_default_window_days=32,
                monitoring_max_window_days=31,
            )
        )


def test_settings_reject_monitoring_default_page_size_larger_than_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                monitoring_default_page_size=201,
                monitoring_max_page_size=200,
            )
        )


def test_settings_reject_dashboard_default_limit_larger_than_maximum() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                dashboard_default_worst_performers_limit=51,
                dashboard_max_worst_performers_limit=50,
            )
        )


def test_settings_reject_dashboard_max_limit_above_phase7_cap() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                dashboard_max_worst_performers_limit=(
                    DASHBOARD_MAX_WORST_PERFORMERS_LIMIT + 1
                ),
            )
        )


def test_settings_reject_invalid_monitoring_recent_history_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_settings(
                monitoring_default_recent_history_limit=0,
            )
        )


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


def test_phase5_metric_registry_constants_remain_aligned() -> None:
    assert GRADING_METRICS_SCORE_KEYS == (
        "relevancy",
        "accuracy",
        "completeness",
        "clarity",
        "tone",
        "repetition",
        "satisfaction",
        "frustration",
    )
    assert GRADING_METRICS_OUTCOME_RATE_KEYS == (
        "resolution_rate_pct",
        "loop_detected_rate_pct",
        "non_genuine_rate_pct",
        "escalation_rate_pct",
        "escalation_failure_rate_pct",
    )
    assert GRADING_RUN_SUCCESSFUL_STATUSES == {
        "completed",
        "completed_with_failures",
    }
    assert len(INTENT_CODES) == 16
    assert INTENT_CODE_TO_CATEGORY["unknown"] == "System Fallback"
    assert INTENT_CATEGORIES == (
        "Policy Related",
        "Claims Related",
        "Billing & Payments",
        "Documents & Admin",
        "Support & Complaints",
        "Non-genuine",
        "System Fallback",
    )
    assert MONITORING_ALLOWED_SORT_FIELDS == (
        "frustration_score",
        "accuracy_score",
    )
    assert MONITORING_ALLOWED_SORT_DIRECTIONS == ("asc", "desc")
    assert DASHBOARD_DEFAULT_WINDOW_DAYS == 7
    assert DASHBOARD_MAX_WINDOW_DAYS == 31
    assert DASHBOARD_DEFAULT_WORST_PERFORMERS_LIMIT == 10
    assert DASHBOARD_MAX_WORST_PERFORMERS_LIMIT == 50
    assert DASHBOARD_HEATMAP_SCORE_BUCKETS == (
        ("1-4", 1, 4),
        ("5-7", 5, 7),
        ("8-10", 8, 10),
    )
    assert DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS == (
        ("1-2", 1, 2),
        ("3-4", 3, 4),
        ("5-6", 5, 6),
        ("7-8", 7, 8),
        ("9-10", 9, 10),
    )
    assert DASHBOARD_ATTENTION_SIGNAL_THRESHOLDS == {
        "failure_escalation_rate_pct": 10.0,
        "dimension_average_low": 7.5,
    }
    assert DASHBOARD_STORY_CARD_SEVERITY_THRESHOLDS == (
        ("critical", 10.0),
        ("warning", 5.0),
        ("info", 0.0),
    )
