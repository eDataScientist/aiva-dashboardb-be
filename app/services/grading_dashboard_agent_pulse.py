from __future__ import annotations

from datetime import date as calendar_date

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import (
    DASHBOARD_ATTENTION_SIGNAL_THRESHOLDS,
    GRADING_ESCALATION_TYPE_VALUES,
    INTENT_CODE_TO_CATEGORY,
    INTENT_CODE_TO_LABEL,
)
from app.models.conversation_grades import ConversationGrade
from app.schemas.grading_dashboard_agent_pulse import (
    GradingDashboardAgentPulseAttentionSignal,
    GradingDashboardAgentPulseDimensionAverages,
    GradingDashboardAgentPulseEscalationBreakdownItem,
    GradingDashboardAgentPulseHealth,
    GradingDashboardAgentPulseResponse,
    GradingDashboardAgentPulseTrendPoint,
    GradingDashboardAgentPulseTopIntentTag,
    GradingDashboardAgentPulseUserSignals,
)
from app.schemas.grading_dashboard_common import (
    GradingDashboardFreshness,
    GradingDashboardInsightSeverity,
    GradingDashboardWindowQuery,
)
from app.services.grading_metrics import (
    GradingMetricsDateWindow,
    build_latest_successful_grading_run_stmt,
    iter_grading_metrics_dates,
)

_AI_PERF_PAIRS: tuple[tuple[str, str], ...] = (
    ("relevancy", "relevancy_score"),
    ("accuracy", "accuracy_score"),
    ("completeness", "completeness_score"),
    ("clarity", "clarity_score"),
    ("tone", "tone_score"),
)

_SEVERITY_ORDER: dict[GradingDashboardInsightSeverity, int] = {
    GradingDashboardInsightSeverity.CRITICAL: 0,
    GradingDashboardInsightSeverity.WARNING: 1,
    GradingDashboardInsightSeverity.INFO: 2,
}
_ATTENTION_SIGNAL_PRIORITY: dict[str, int] = {
    "escalation_failure_rate_high": 0,
    "dimension_accuracy_low": 1,
    "dimension_clarity_low": 2,
    "dimension_completeness_low": 3,
    "dimension_relevancy_low": 4,
    "dimension_tone_low": 5,
}


def build_grading_dashboard_agent_pulse_stmt(
    *,
    start_date: calendar_date,
    end_date: calendar_date,
) -> Select[tuple[ConversationGrade]]:
    return select(ConversationGrade).where(
        ConversationGrade.grade_date >= start_date,
        ConversationGrade.grade_date <= end_date,
    )


def _to_float(value: object) -> float:
    return round(float(value or 0.0), 4)


def _to_pct(count: object, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((float(count or 0.0) / float(total)) * 100.0, 4)


def derive_agent_pulse_attention_signals(
    *,
    dimension_averages: GradingDashboardAgentPulseDimensionAverages,
    escalation_failure_rate_pct: float,
    total: int,
) -> list[GradingDashboardAgentPulseAttentionSignal]:
    """Return deterministic threshold-driven attention signals in stable severity order."""
    if total == 0:
        return []

    failure_threshold = DASHBOARD_ATTENTION_SIGNAL_THRESHOLDS["failure_escalation_rate_pct"]
    dim_low_threshold = DASHBOARD_ATTENTION_SIGNAL_THRESHOLDS["dimension_average_low"]

    signals: list[GradingDashboardAgentPulseAttentionSignal] = []

    if escalation_failure_rate_pct >= failure_threshold:
        signals.append(
            GradingDashboardAgentPulseAttentionSignal(
                code="escalation_failure_rate_high",
                severity=GradingDashboardInsightSeverity.WARNING,
                label="High Failure Escalation Rate",
                metric_key="escalation_failure_rate_pct",
                value=round(escalation_failure_rate_pct, 2),
                message=(
                    f"Failure escalation rate is "
                    f"{round(escalation_failure_rate_pct, 1)}%, "
                    f"exceeding the {failure_threshold}% threshold."
                ),
            )
        )

    dim_checks = (
        ("relevancy", dimension_averages.relevancy),
        ("accuracy", dimension_averages.accuracy),
        ("completeness", dimension_averages.completeness),
        ("clarity", dimension_averages.clarity),
        ("tone", dimension_averages.tone),
    )
    for dim_key, dim_val in dim_checks:
        if dim_val < dim_low_threshold:
            signals.append(
                GradingDashboardAgentPulseAttentionSignal(
                    code=f"dimension_{dim_key}_low",
                    severity=GradingDashboardInsightSeverity.WARNING,
                    label=f"Low {dim_key.capitalize()} Score",
                    metric_key=f"avg_{dim_key}_score",
                    value=round(dim_val, 2),
                    message=(
                        f"Average {dim_key} score is {round(dim_val, 1)}, "
                        f"below the {dim_low_threshold} threshold."
                    ),
                )
            )

    signals.sort(
        key=lambda s: (
            _SEVERITY_ORDER[s.severity],
            _ATTENTION_SIGNAL_PRIORITY.get(s.code, 999),
            s.code,
        )
    )
    return signals


async def get_grading_dashboard_agent_pulse(
    session: AsyncSession,
    query: GradingDashboardWindowQuery,
) -> GradingDashboardAgentPulseResponse:
    start_date: calendar_date = query.start_date  # type: ignore[assignment]
    end_date: calendar_date = query.end_date  # type: ignore[assignment]

    grades = build_grading_dashboard_agent_pulse_stmt(
        start_date=start_date,
        end_date=end_date,
    ).subquery()

    # --- Summary aggregate ---
    dim_avg_exprs = [
        func.coalesce(func.avg(getattr(grades.c, col)), 0.0).label(key)
        for key, col in _AI_PERF_PAIRS
    ]
    summary_row = (
        await session.execute(
            select(
                func.count(grades.c.id).label("total"),
                *dim_avg_exprs,
                func.coalesce(func.avg(grades.c.repetition_score), 0.0).label(
                    "avg_repetition"
                ),
                func.sum(
                    case((grades.c.resolution.is_(True), 1), else_=0)
                ).label("resolution_count"),
                func.sum(
                    case((grades.c.loop_detected.is_(True), 1), else_=0)
                ).label("loop_count"),
                func.sum(
                    case((grades.c.user_relevancy.is_(True), 1), else_=0)
                ).label("user_relevancy_count"),
                func.coalesce(func.avg(grades.c.satisfaction_score), 0.0).label(
                    "avg_satisfaction"
                ),
                func.coalesce(func.avg(grades.c.frustration_score), 0.0).label(
                    "avg_frustration"
                ),
                func.sum(
                    case((grades.c.escalation_type == "Failure", 1), else_=0)
                ).label("escalation_failure_count"),
            )
        )
    ).one()._mapping

    total = int(summary_row["total"] or 0)

    dim_averages = GradingDashboardAgentPulseDimensionAverages(
        relevancy=_to_float(summary_row["relevancy"]),
        accuracy=_to_float(summary_row["accuracy"]),
        completeness=_to_float(summary_row["completeness"]),
        clarity=_to_float(summary_row["clarity"]),
        tone=_to_float(summary_row["tone"]),
    )
    overall_composite = round(
        (
            dim_averages.relevancy
            + dim_averages.accuracy
            + dim_averages.completeness
            + dim_averages.clarity
            + dim_averages.tone
        )
        / 5.0,
        4,
    )

    escalation_failure_rate = _to_pct(summary_row["escalation_failure_count"], total)
    health = GradingDashboardAgentPulseHealth(
        resolution_rate_pct=_to_pct(summary_row["resolution_count"], total),
        avg_repetition_score=_to_float(summary_row["avg_repetition"]),
        loop_detected_rate_pct=_to_pct(summary_row["loop_count"], total),
    )
    user_signals = GradingDashboardAgentPulseUserSignals(
        avg_satisfaction_score=_to_float(summary_row["avg_satisfaction"]),
        avg_frustration_score=_to_float(summary_row["avg_frustration"]),
        user_relevancy_rate_pct=_to_pct(summary_row["user_relevancy_count"], total),
    )

    # --- Escalation breakdown ---
    esc_rows = (
        await session.execute(
            select(
                grades.c.escalation_type,
                func.count(grades.c.id).label("count"),
            )
            .where(grades.c.escalation_type.is_not(None))
            .group_by(grades.c.escalation_type)
        )
    ).mappings().all()
    counts_by_type = {
        str(row["escalation_type"]): int(row["count"] or 0) for row in esc_rows
    }
    escalation_breakdown = [
        GradingDashboardAgentPulseEscalationBreakdownItem(
            escalation_type=esc_type,
            count=counts_by_type.get(esc_type, 0),
            share_pct=_to_pct(counts_by_type.get(esc_type, 0), total),
        )
        for esc_type in GRADING_ESCALATION_TYPE_VALUES
    ]

    # --- Daily trend points (zero-filled across the window) ---
    trend_rows = (
        await session.execute(
            select(
                grades.c.grade_date.label("date"),
                (
                    (
                        func.coalesce(func.avg(grades.c.relevancy_score), 0.0)
                        + func.coalesce(func.avg(grades.c.accuracy_score), 0.0)
                        + func.coalesce(func.avg(grades.c.completeness_score), 0.0)
                        + func.coalesce(func.avg(grades.c.clarity_score), 0.0)
                        + func.coalesce(func.avg(grades.c.tone_score), 0.0)
                    )
                    / 5.0
                ).label("overall_composite"),
                func.coalesce(func.avg(grades.c.satisfaction_score), 0.0).label(
                    "avg_satisfaction"
                ),
                func.coalesce(func.avg(grades.c.frustration_score), 0.0).label(
                    "avg_frustration"
                ),
            )
            .group_by(grades.c.grade_date)
            .order_by(grades.c.grade_date)
        )
    ).mappings().all()
    trend_by_date = {row["date"]: row for row in trend_rows}

    window = GradingMetricsDateWindow(
        start_date=start_date,  # type: ignore[arg-type]
        end_date=end_date,  # type: ignore[arg-type]
    )
    trend_points: list[GradingDashboardAgentPulseTrendPoint] = []
    for d in iter_grading_metrics_dates(window):
        row = trend_by_date.get(d)
        trend_points.append(
            GradingDashboardAgentPulseTrendPoint(
                date=d,
                overall_composite_score=_to_float(
                    None if row is None else row["overall_composite"]
                ),
                satisfaction_score=_to_float(
                    None if row is None else row["avg_satisfaction"]
                ),
                frustration_score=_to_float(
                    None if row is None else row["avg_frustration"]
                ),
            )
        )

    # --- Top intents (ordered by count DESC, then code for stability) ---
    intent_rows = (
        await session.execute(
            select(
                grades.c.intent_code,
                func.count(grades.c.id).label("count"),
            )
            .where(grades.c.intent_code.is_not(None))
            .where(grades.c.intent_code.in_(list(INTENT_CODE_TO_LABEL.keys())))
            .group_by(grades.c.intent_code)
            .order_by(func.count(grades.c.id).desc(), grades.c.intent_code)
        )
    ).mappings().all()
    top_intents = [
        GradingDashboardAgentPulseTopIntentTag(
            intent_code=str(row["intent_code"]),
            intent_label=INTENT_CODE_TO_LABEL[str(row["intent_code"])],
            intent_category=INTENT_CODE_TO_CATEGORY[str(row["intent_code"])],
            count=int(row["count"] or 0),
        )
        for row in intent_rows
        if str(row["intent_code"]) in INTENT_CODE_TO_LABEL
    ][:6]

    # --- Attention signals ---
    attention_signals = derive_agent_pulse_attention_signals(
        dimension_averages=dim_averages,
        escalation_failure_rate_pct=escalation_failure_rate,
        total=total,
    )

    # --- Freshness (latest-successful grading run, independent of window data) ---
    run = await session.scalar(build_latest_successful_grading_run_stmt())
    freshness = GradingDashboardFreshness(
        latest_successful_run_id=None if run is None else run.id,
        latest_successful_window_end_date=None if run is None else run.target_end_date,
        latest_successful_run_finished_at=None if run is None else run.finished_at,
    )

    return GradingDashboardAgentPulseResponse(
        date_window=query.date_window,
        total_graded_customer_days=total,
        overall_composite_score=overall_composite,
        dimension_averages=dim_averages,
        health=health,
        escalation_breakdown=escalation_breakdown,
        user_signals=user_signals,
        trend_points=trend_points,
        top_intents=top_intents,
        attention_signals=attention_signals,
        freshness=freshness,
    )
