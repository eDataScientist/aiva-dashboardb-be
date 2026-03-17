from __future__ import annotations

from datetime import date as calendar_date
from typing import Final

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import (
    DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS,
    DASHBOARD_HEATMAP_SCORE_BUCKETS,
    DASHBOARD_STORY_CARD_SEVERITY_THRESHOLDS,
)
from app.models.conversation_grades import ConversationGrade
from app.schemas.grading_dashboard_common import (
    GradingDashboardFreshness,
    GradingDashboardWindowQuery,
)
from app.schemas.grading_dashboard_correlations import (
    GradingDashboardCorrelationFrustrationHistogramBucket,
    GradingDashboardCorrelationFunnelStep,
    GradingDashboardCorrelationHeatmapCell,
    GradingDashboardCorrelationStoryCard,
    GradingDashboardCorrelationsResponse,
)
from app.services.grading_metrics import get_latest_successful_grading_metrics_freshness

_CORRELATION_DIMENSIONS: Final[tuple[tuple[str, str], ...]] = (
    ("relevancy", "Relevancy"),
    ("accuracy", "Accuracy"),
    ("completeness", "Completeness"),
    ("clarity", "Clarity"),
    ("tone", "Tone"),
)
_FAILURE_FUNNEL_FRUSTRATION_MIN: Final[int] = 7
_STORY_CARD_PRIORITY: Final[dict[str, int]] = {
    "failure_escalation_rate": 0,
    "unresolved_rate": 1,
    "high_frustration_rate": 2,
    "loop_detected_rate": 3,
}
_STORY_CARD_METADATA: Final[tuple[tuple[str, str, str, str], ...]] = (
    (
        "failure_escalation_rate",
        "Failure Escalations",
        "failure_escalation_rate_pct",
        "Failure escalations affected {value:.2f}% of graded customer-days in the selected window.",
    ),
    (
        "unresolved_rate",
        "Unresolved Conversations",
        "unresolved_rate_pct",
        "Unresolved conversations affected {value:.2f}% of graded customer-days in the selected window.",
    ),
    (
        "high_frustration_rate",
        "High Frustration",
        "high_frustration_rate_pct",
        "High-frustration conversations affected {value:.2f}% of graded customer-days in the selected window.",
    ),
    (
        "loop_detected_rate",
        "Loop Detection",
        "loop_detected_rate_pct",
        "Loop-detected conversations affected {value:.2f}% of graded customer-days in the selected window.",
    ),
)
_SEVERITY_SORT_ORDER: Final[dict[str, int]] = {
    "critical": 0,
    "warning": 1,
    "info": 2,
}


def build_grading_dashboard_correlations_stmt(
    *,
    start_date: calendar_date,
    end_date: calendar_date,
) -> Select[tuple[ConversationGrade]]:
    return select(ConversationGrade).where(
        ConversationGrade.grade_date >= start_date,
        ConversationGrade.grade_date <= end_date,
    )


async def get_grading_dashboard_correlations(
    session: AsyncSession,
    query: GradingDashboardWindowQuery,
) -> GradingDashboardCorrelationsResponse:
    grades = (
        await session.scalars(
            build_grading_dashboard_correlations_stmt(
                start_date=query.start_date,  # type: ignore[arg-type]
                end_date=query.end_date,  # type: ignore[arg-type]
            )
        )
    ).all()
    freshness_record = await get_latest_successful_grading_metrics_freshness(session)

    return GradingDashboardCorrelationsResponse(
        date_window=query.date_window,
        total_graded_customer_days=len(grades),
        heatmap_cells=_build_heatmap_cells(grades),
        failure_funnel=_build_failure_funnel(grades),
        frustration_histogram=_build_frustration_histogram(grades),
        story_cards=_build_story_cards(grades),
        freshness=GradingDashboardFreshness(
            latest_successful_run_id=(
                None if freshness_record is None else freshness_record.run_id
            ),
            latest_successful_window_end_date=(
                None if freshness_record is None else freshness_record.target_end_date
            ),
            latest_successful_run_finished_at=(
                None if freshness_record is None else freshness_record.finished_at
            ),
        ),
    )


def _build_heatmap_cells(
    grades: list[ConversationGrade],
) -> list[GradingDashboardCorrelationHeatmapCell]:
    cells: list[GradingDashboardCorrelationHeatmapCell] = []
    for dimension_key, dimension_label in _CORRELATION_DIMENSIONS:
        score_attr = f"{dimension_key}_score"
        for bucket_label, min_score, max_score in DASHBOARD_HEATMAP_SCORE_BUCKETS:
            matching_grades = [
                grade
                for grade in grades
                if (
                    getattr(grade, score_attr) is not None
                    and min_score <= getattr(grade, score_attr) <= max_score
                )
            ]
            satisfaction_values = [
                float(grade.satisfaction_score)
                for grade in matching_grades
                if grade.satisfaction_score is not None
            ]
            avg_satisfaction = (
                round(sum(satisfaction_values) / len(satisfaction_values), 2)
                if satisfaction_values
                else 0.0
            )
            cells.append(
                GradingDashboardCorrelationHeatmapCell(
                    dimension_key=dimension_key,
                    dimension_label=dimension_label,
                    score_bucket=bucket_label,
                    conversation_count=len(matching_grades),
                    avg_satisfaction_score=avg_satisfaction,
                )
            )
    return cells


def _build_failure_funnel(
    grades: list[ConversationGrade],
) -> list[GradingDashboardCorrelationFunnelStep]:
    loop_detected = [grade for grade in grades if grade.loop_detected is True]
    high_frustration = [
        grade
        for grade in loop_detected
        if grade.frustration_score is not None
        and grade.frustration_score >= _FAILURE_FUNNEL_FRUSTRATION_MIN
    ]
    unresolved = [grade for grade in high_frustration if grade.resolution is False]
    failure_escalations = [
        grade for grade in unresolved if grade.escalation_type == "Failure"
    ]

    return [
        GradingDashboardCorrelationFunnelStep(
            step_key="total",
            label="Total",
            count=len(grades),
        ),
        GradingDashboardCorrelationFunnelStep(
            step_key="loop_detected",
            label="Loop Detected",
            count=len(loop_detected),
        ),
        GradingDashboardCorrelationFunnelStep(
            step_key="high_frustration",
            label="High Frustration",
            count=len(high_frustration),
        ),
        GradingDashboardCorrelationFunnelStep(
            step_key="unresolved",
            label="Unresolved",
            count=len(unresolved),
        ),
        GradingDashboardCorrelationFunnelStep(
            step_key="failure_escalation",
            label="Failure Escalation",
            count=len(failure_escalations),
        ),
    ]


def _build_frustration_histogram(
    grades: list[ConversationGrade],
) -> list[GradingDashboardCorrelationFrustrationHistogramBucket]:
    total = len(grades)
    buckets: list[GradingDashboardCorrelationFrustrationHistogramBucket] = []
    for bucket_label, min_score, max_score in DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS:
        count = sum(
            1
            for grade in grades
            if grade.frustration_score is not None
            and min_score <= grade.frustration_score <= max_score
        )
        buckets.append(
            GradingDashboardCorrelationFrustrationHistogramBucket(
                bucket_label=bucket_label,
                min_score=min_score,
                max_score=max_score,
                count=count,
                share_pct=_to_pct(count, total),
            )
        )
    return buckets


def _build_story_cards(
    grades: list[ConversationGrade],
) -> list[GradingDashboardCorrelationStoryCard]:
    total = len(grades)
    metric_values = {
        "failure_escalation_rate": _to_pct(
            sum(1 for grade in grades if grade.escalation_type == "Failure"),
            total,
        ),
        "unresolved_rate": _to_pct(
            sum(1 for grade in grades if grade.resolution is False),
            total,
        ),
        "high_frustration_rate": _to_pct(
            sum(
                1
                for grade in grades
                if grade.frustration_score is not None
                and grade.frustration_score >= _FAILURE_FUNNEL_FRUSTRATION_MIN
            ),
            total,
        ),
        "loop_detected_rate": _to_pct(
            sum(1 for grade in grades if grade.loop_detected is True),
            total,
        ),
    }

    story_cards = [
        GradingDashboardCorrelationStoryCard(
            code=code,
            severity=_resolve_story_card_severity(metric_values[code]),
            title=title,
            metric_key=metric_key,
            metric_value=metric_values[code],
            explanation=message_template.format(value=metric_values[code]),
        )
        for code, title, metric_key, message_template in _STORY_CARD_METADATA
    ]
    return sorted(
        story_cards,
        key=lambda card: (
            _SEVERITY_SORT_ORDER[card.severity.value],
            _STORY_CARD_PRIORITY[card.code],
        ),
    )


def _resolve_story_card_severity(metric_value: float) -> str:
    for severity, threshold in DASHBOARD_STORY_CARD_SEVERITY_THRESHOLDS:
        if metric_value >= threshold:
            return severity
    return "info"


def _to_pct(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(float(value) / float(total) * 100.0, 2)
