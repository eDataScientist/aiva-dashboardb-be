from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select

from app.core import HIGHLIGHT_CODE_TO_LABEL
from app.models.monitoring_highlight_config import MonitoringHighlightConfig


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


def canonical_monitoring_highlight_labels() -> dict[str, str]:
    return dict(HIGHLIGHT_CODE_TO_LABEL)
