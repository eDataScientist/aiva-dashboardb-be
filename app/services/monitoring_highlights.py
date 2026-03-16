from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import HIGHLIGHT_CODE_TO_LABEL, HIGHLIGHT_CODES
from app.models.conversation_grades import ConversationGrade
from app.models.monitoring_highlight_config import MonitoringHighlightConfig
from app.schemas.grading_monitoring import MonitoringHighlightBadge

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MonitoringHighlightRuleSet:
    frustration_min_threshold: int
    failure_escalation_enabled: bool
    loop_detected_enabled: bool
    accuracy_max_threshold: int
    unresolved_low_satisfaction_enabled: bool
    unresolved_satisfaction_max_threshold: int
    user_irrelevancy_enabled: bool


def get_monitoring_highlight_defaults() -> MonitoringHighlightRuleSet:
    return MonitoringHighlightRuleSet(
        frustration_min_threshold=7,
        failure_escalation_enabled=True,
        loop_detected_enabled=True,
        accuracy_max_threshold=3,
        unresolved_low_satisfaction_enabled=True,
        unresolved_satisfaction_max_threshold=3,
        user_irrelevancy_enabled=True,
    )


def build_active_monitoring_highlight_config_stmt() -> Select[tuple[MonitoringHighlightConfig]]:
    return (
        select(MonitoringHighlightConfig)
        .where(MonitoringHighlightConfig.is_active.is_(True))
        .order_by(
            MonitoringHighlightConfig.updated_at.desc(),
            MonitoringHighlightConfig.id.desc(),
        )
        .limit(1)
    )


def _build_active_monitoring_highlight_rule_values_stmt() -> Select[
    tuple[int, bool, bool, int, bool, int, bool]
]:
    return (
        select(
            MonitoringHighlightConfig.frustration_min_threshold,
            MonitoringHighlightConfig.failure_escalation_enabled,
            MonitoringHighlightConfig.loop_detected_enabled,
            MonitoringHighlightConfig.accuracy_max_threshold,
            MonitoringHighlightConfig.unresolved_low_satisfaction_enabled,
            MonitoringHighlightConfig.unresolved_satisfaction_max_threshold,
            MonitoringHighlightConfig.user_irrelevancy_enabled,
        )
        .where(MonitoringHighlightConfig.is_active.is_(True))
        .order_by(
            MonitoringHighlightConfig.updated_at.desc(),
            MonitoringHighlightConfig.id.desc(),
        )
        .limit(1)
    )


def _rule_set_from_values(
    *,
    frustration_min_threshold: int,
    failure_escalation_enabled: bool,
    loop_detected_enabled: bool,
    accuracy_max_threshold: int,
    unresolved_low_satisfaction_enabled: bool,
    unresolved_satisfaction_max_threshold: int,
    user_irrelevancy_enabled: bool,
) -> MonitoringHighlightRuleSet:
    return MonitoringHighlightRuleSet(
        frustration_min_threshold=frustration_min_threshold,
        failure_escalation_enabled=failure_escalation_enabled,
        loop_detected_enabled=loop_detected_enabled,
        accuracy_max_threshold=accuracy_max_threshold,
        unresolved_low_satisfaction_enabled=unresolved_low_satisfaction_enabled,
        unresolved_satisfaction_max_threshold=unresolved_satisfaction_max_threshold,
        user_irrelevancy_enabled=user_irrelevancy_enabled,
    )


async def load_monitoring_highlight_rules(
    session: AsyncSession,
) -> MonitoringHighlightRuleSet:
    try:
        row = (
            await session.execute(_build_active_monitoring_highlight_rule_values_stmt())
        ).first()
    except SQLAlchemyError:
        logger.warning(
            "Monitoring highlight config read failed; "
            "falling back to seeded defaults."
        )
        return get_monitoring_highlight_defaults()

    if row is None:
        logger.warning(
            "Active monitoring highlight config was unavailable; "
            "falling back to seeded defaults."
        )
        return get_monitoring_highlight_defaults()

    return _rule_set_from_values(
        frustration_min_threshold=row[0],
        failure_escalation_enabled=row[1],
        loop_detected_enabled=row[2],
        accuracy_max_threshold=row[3],
        unresolved_low_satisfaction_enabled=row[4],
        unresolved_satisfaction_max_threshold=row[5],
        user_irrelevancy_enabled=row[6],
    )


def evaluate_monitoring_highlights(
    grade: ConversationGrade,
    rules: MonitoringHighlightRuleSet,
) -> list[MonitoringHighlightBadge]:
    triggered_codes: list[str] = []

    if (
        grade.frustration_score is not None
        and grade.frustration_score >= rules.frustration_min_threshold
    ):
        triggered_codes.append("frustration_high")
    if (
        rules.failure_escalation_enabled
        and grade.escalation_type_enum is not None
        and grade.escalation_type_enum.value == "Failure"
    ):
        triggered_codes.append("escalation_failure")
    if rules.loop_detected_enabled and grade.loop_detected is True:
        triggered_codes.append("loop_detected")
    if (
        grade.accuracy_score is not None
        and grade.accuracy_score <= rules.accuracy_max_threshold
    ):
        triggered_codes.append("accuracy_low")
    if (
        rules.unresolved_low_satisfaction_enabled
        and grade.resolution is False
        and grade.satisfaction_score is not None
        and grade.satisfaction_score <= rules.unresolved_satisfaction_max_threshold
    ):
        triggered_codes.append("unresolved_low_satisfaction")
    if rules.user_irrelevancy_enabled and grade.user_relevancy is False:
        triggered_codes.append("user_irrelevancy")

    ordered_codes = [code for code in HIGHLIGHT_CODES if code in triggered_codes]
    return [
        MonitoringHighlightBadge(
            code=code,
            label=HIGHLIGHT_CODE_TO_LABEL[code],
        )
        for code in ordered_codes
    ]


def canonical_monitoring_highlight_labels() -> dict[str, str]:
    return dict(HIGHLIGHT_CODE_TO_LABEL)
