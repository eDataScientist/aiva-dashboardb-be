from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from app.core import HIGHLIGHT_CODES
from app.models.conversation_grades import ConversationGrade
from app.models.monitoring_highlight_config import MonitoringHighlightConfig
from app.services import monitoring_highlights as monitoring_highlights_service
from app.services import (
    MonitoringHighlightRuleSet,
    build_active_monitoring_highlight_config_stmt,
    evaluate_monitoring_highlights,
    get_monitoring_highlight_defaults,
    load_monitoring_highlight_rules,
)


def _rule_set_from_config(config: MonitoringHighlightConfig) -> MonitoringHighlightRuleSet:
    return MonitoringHighlightRuleSet(
        frustration_min_threshold=config.frustration_min_threshold,
        failure_escalation_enabled=config.failure_escalation_enabled,
        loop_detected_enabled=config.loop_detected_enabled,
        accuracy_max_threshold=config.accuracy_max_threshold,
        unresolved_low_satisfaction_enabled=config.unresolved_low_satisfaction_enabled,
        unresolved_satisfaction_max_threshold=config.unresolved_satisfaction_max_threshold,
        user_irrelevancy_enabled=config.user_irrelevancy_enabled,
    )


async def _get_seeded_active_config(
    db_session,
) -> MonitoringHighlightConfig:
    config = await db_session.scalar(build_active_monitoring_highlight_config_stmt())
    assert config is not None
    return config


@pytest.mark.asyncio
async def test_load_monitoring_highlight_rules_returns_active_config(db_session) -> None:
    config = await _get_seeded_active_config(db_session)
    config.frustration_min_threshold = 8
    config.failure_escalation_enabled = False
    config.loop_detected_enabled = True
    config.accuracy_max_threshold = 2
    config.unresolved_low_satisfaction_enabled = False
    config.unresolved_satisfaction_max_threshold = 4
    config.user_irrelevancy_enabled = False
    await db_session.flush()

    rules = await load_monitoring_highlight_rules(db_session)

    assert rules == _rule_set_from_config(config)


@pytest.mark.asyncio
async def test_load_monitoring_highlight_rules_falls_back_to_defaults_when_missing(
    db_session,
) -> None:
    await db_session.execute(delete(MonitoringHighlightConfig))
    await db_session.flush()

    with patch.object(monitoring_highlights_service.logger, "warning") as warning_mock:
        rules = await load_monitoring_highlight_rules(db_session)

    assert rules == get_monitoring_highlight_defaults()
    warning_mock.assert_called_once()
    assert "monitoring highlight config" in warning_mock.call_args.args[0].lower()
    assert "falling back to seeded defaults" in warning_mock.call_args.args[0].lower()


def _grade(**overrides: object) -> ConversationGrade:
    values: dict[str, object] = {
        "frustration_score": 2,
        "escalation_type": "None",
        "loop_detected": False,
        "accuracy_score": 8,
        "resolution": True,
        "satisfaction_score": 8,
        "user_relevancy": True,
    }
    values.update(overrides)
    return ConversationGrade(**values)


def test_evaluate_monitoring_highlights_returns_canonical_badges_in_stable_order() -> None:
    rules = MonitoringHighlightRuleSet(
        frustration_min_threshold=7,
        failure_escalation_enabled=True,
        loop_detected_enabled=True,
        accuracy_max_threshold=3,
        unresolved_low_satisfaction_enabled=True,
        unresolved_satisfaction_max_threshold=3,
        user_irrelevancy_enabled=True,
    )

    badges = evaluate_monitoring_highlights(
        _grade(
            frustration_score=9,
            escalation_type="Failure",
            loop_detected=True,
            accuracy_score=2,
            resolution=False,
            satisfaction_score=2,
            user_relevancy=False,
        ),
        rules,
    )

    assert [badge.code for badge in badges] == list(HIGHLIGHT_CODES)
    assert [badge.label for badge in badges] == [
        "High Frustration",
        "Failed Escalation",
        "Conversation Loop",
        "Low Accuracy",
        "Unresolved + Low Satisfaction",
        "Non-genuine Interaction",
    ]


@pytest.mark.parametrize(
    ("grade_overrides", "expected_code"),
    [
        ({"frustration_score": 7}, "frustration_high"),
        ({"escalation_type": "Failure"}, "escalation_failure"),
        ({"loop_detected": True}, "loop_detected"),
        ({"accuracy_score": 3}, "accuracy_low"),
        (
            {"resolution": False, "satisfaction_score": 3},
            "unresolved_low_satisfaction",
        ),
        ({"user_relevancy": False}, "user_irrelevancy"),
    ],
)
def test_evaluate_monitoring_highlights_triggers_each_canonical_badge_independently(
    grade_overrides: dict[str, object],
    expected_code: str,
) -> None:
    badges = evaluate_monitoring_highlights(
        _grade(**grade_overrides),
        get_monitoring_highlight_defaults(),
    )

    assert [badge.code for badge in badges] == [expected_code]


def test_evaluate_monitoring_highlights_respects_thresholds_and_disabled_toggles() -> None:
    rules = MonitoringHighlightRuleSet(
        frustration_min_threshold=8,
        failure_escalation_enabled=False,
        loop_detected_enabled=False,
        accuracy_max_threshold=2,
        unresolved_low_satisfaction_enabled=False,
        unresolved_satisfaction_max_threshold=2,
        user_irrelevancy_enabled=False,
    )

    badges = evaluate_monitoring_highlights(
        _grade(
            frustration_score=7,
            escalation_type="Failure",
            loop_detected=True,
            accuracy_score=3,
            resolution=False,
            satisfaction_score=2,
            user_relevancy=False,
        ),
        rules,
    )

    assert badges == []


@pytest.mark.asyncio
async def test_load_monitoring_highlight_rules_ignores_inactive_rows_and_warns(
    db_session,
) -> None:
    config = await _get_seeded_active_config(db_session)
    config.is_active = False
    await db_session.flush()

    with patch.object(monitoring_highlights_service.logger, "warning") as warning_mock:
        rules = await load_monitoring_highlight_rules(db_session)

    assert rules == get_monitoring_highlight_defaults()
    warning_mock.assert_called_once()
    assert "monitoring highlight config" in warning_mock.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_load_monitoring_highlight_rules_falls_back_to_defaults_when_read_fails(
    db_session,
) -> None:
    with (
        patch.object(
            db_session,
            "execute",
            AsyncMock(side_effect=SQLAlchemyError("config read failed")),
        ),
        patch.object(monitoring_highlights_service.logger, "warning") as warning_mock,
    ):
        rules = await load_monitoring_highlight_rules(db_session)

    assert rules == get_monitoring_highlight_defaults()
    warning_mock.assert_called_once()
    assert "monitoring highlight config read failed" in warning_mock.call_args.args[0].lower()
    assert "falling back to seeded defaults" in warning_mock.call_args.args[0].lower()
