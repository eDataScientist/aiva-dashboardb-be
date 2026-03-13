from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import (
    GRADING_ESCALATION_TYPE_VALUES,
    GRADING_METRICS_SCORE_TO_COLUMN,
    GRADING_RUN_SUCCESSFUL_STATUSES,
    INTENT_CODES,
    INTENT_CODE_TO_CATEGORY,
    INTENT_CODE_TO_LABEL,
)
from app.models.conversation_grades import ConversationGrade
from app.models.grading_runs import GradingRun
from app.schemas.grading_metrics import (
    GradingIntentDistributionItem,
    GradingIntentDistributionResponse,
    GradingIntentTrendPoint,
    GradingIntentTrendResponse,
    GradingIntentTrendSeries,
    GradingMetricsAverageScores,
    GradingMetricsDateWindow as GradingMetricsDateWindowSchema,
    GradingMetricsEscalationBreakdownItem,
    GradingMetricsFreshness,
    GradingMetricsIntentTrendQuery,
    GradingMetricsOutcomeRates,
    GradingMetricsSummaryResponse,
    GradingMetricsWindowQuery,
    GradingOutcomeTrendPoint,
    GradingOutcomeTrendResponse,
    GradingScoreTrendPoint,
    GradingScoreTrendResponse,
)


@dataclass(frozen=True, slots=True)
class GradingMetricsDateWindow:
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class GradingMetricsFreshnessRecord:
    run_id: UUID
    target_end_date: date
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class GradingMetricsSummaryAggregate:
    date_window: GradingMetricsDateWindow
    total_graded_customer_days: int
    average_scores: GradingMetricsAverageScores
    outcome_rates: GradingMetricsOutcomeRates


def resolve_grading_metrics_window(
    query: GradingMetricsWindowQuery,
) -> GradingMetricsDateWindow:
    return GradingMetricsDateWindow(
        start_date=query.start_date,  # type: ignore[arg-type]
        end_date=query.end_date,  # type: ignore[arg-type]
    )


def iter_grading_metrics_dates(window: GradingMetricsDateWindow) -> tuple[date, ...]:
    current_date = window.start_date
    points: list[date] = []
    while current_date <= window.end_date:
        points.append(current_date)
        current_date += timedelta(days=1)
    return tuple(points)


def build_grading_metrics_base_stmt(
    window: GradingMetricsDateWindow,
    *,
    intent_codes: Sequence[str] = (),
) -> Select[tuple[ConversationGrade]]:
    stmt = select(ConversationGrade).where(
        ConversationGrade.grade_date >= window.start_date,
        ConversationGrade.grade_date <= window.end_date,
    )
    if intent_codes:
        stmt = stmt.where(ConversationGrade.intent_code.in_(tuple(intent_codes)))
    return stmt


def build_summary_grades_stmt(
    window: GradingMetricsDateWindow,
) -> Select[tuple[ConversationGrade]]:
    return build_grading_metrics_base_stmt(window)


def build_score_trend_grades_stmt(
    window: GradingMetricsDateWindow,
) -> Select[tuple[ConversationGrade]]:
    return build_grading_metrics_base_stmt(window)


def build_outcome_trend_grades_stmt(
    window: GradingMetricsDateWindow,
) -> Select[tuple[ConversationGrade]]:
    return build_grading_metrics_base_stmt(window)


def build_intent_distribution_grades_stmt(
    window: GradingMetricsDateWindow,
    *,
    intent_codes: Sequence[str] = (),
) -> Select[tuple[ConversationGrade]]:
    return build_grading_metrics_base_stmt(window, intent_codes=intent_codes)


def build_intent_trend_grades_stmt(
    query: GradingMetricsIntentTrendQuery,
) -> Select[tuple[ConversationGrade]]:
    return build_grading_metrics_base_stmt(
        resolve_grading_metrics_window(query),
        intent_codes=query.intent_codes,
    )


def build_latest_successful_grading_run_stmt() -> Select[tuple[GradingRun]]:
    return (
        select(GradingRun)
        .where(GradingRun.status.in_(tuple(sorted(GRADING_RUN_SUCCESSFUL_STATUSES))))
        .order_by(
            GradingRun.finished_at.desc().nulls_last(),
            GradingRun.created_at.desc(),
            GradingRun.id.desc(),
        )
        .limit(1)
    )


async def get_grading_metrics_summary_aggregate(
    session: AsyncSession,
    *,
    window: GradingMetricsDateWindow,
) -> GradingMetricsSummaryAggregate:
    grades = build_summary_grades_stmt(window).subquery()
    score_avg_labels = tuple(GRADING_METRICS_SCORE_TO_COLUMN.keys())
    score_avg_exprs = [
        func.avg(getattr(grades.c, column_name)).label(metric_key)
        for metric_key, column_name in GRADING_METRICS_SCORE_TO_COLUMN.items()
    ]
    outcome_sum_exprs = [
        func.sum(case((grades.c.resolution.is_(True), 1), else_=0)).label(
            "resolution_count"
        ),
        func.sum(case((grades.c.loop_detected.is_(True), 1), else_=0)).label(
            "loop_detected_count"
        ),
        func.sum(case((grades.c.user_relevancy.is_(False), 1), else_=0)).label(
            "non_genuine_count"
        ),
        func.sum(case((grades.c.escalation_occurred.is_(True), 1), else_=0)).label(
            "escalation_count"
        ),
        func.sum(case((grades.c.escalation_type == "Failure", 1), else_=0)).label(
            "escalation_failure_count"
        ),
    ]
    result = await session.execute(
        select(
            func.count(grades.c.id).label("total_graded_customer_days"),
            *score_avg_exprs,
            *outcome_sum_exprs,
        )
    )
    row = result.one()._mapping
    total = int(row["total_graded_customer_days"] or 0)

    average_scores = GradingMetricsAverageScores(
        **{
            metric_key: float(row[metric_key] or 0.0)
            for metric_key in score_avg_labels
        }
    )
    outcome_rates = GradingMetricsOutcomeRates(
        resolution_rate_pct=_to_pct(row["resolution_count"], total),
        loop_detected_rate_pct=_to_pct(row["loop_detected_count"], total),
        non_genuine_rate_pct=_to_pct(row["non_genuine_count"], total),
        escalation_rate_pct=_to_pct(row["escalation_count"], total),
        escalation_failure_rate_pct=_to_pct(row["escalation_failure_count"], total),
    )
    return GradingMetricsSummaryAggregate(
        date_window=window,
        total_graded_customer_days=total,
        average_scores=average_scores,
        outcome_rates=outcome_rates,
    )


def _to_pct(value: object, total: int) -> float:
    if total <= 0:
        return 0.0
    return (float(value or 0.0) / float(total)) * 100.0


def _to_score_value(value: object) -> float:
    return round(float(value or 0.0), 2)


async def get_grading_metrics_summary(
    session: AsyncSession,
    query: GradingMetricsWindowQuery,
) -> GradingMetricsSummaryResponse:
    window = resolve_grading_metrics_window(query)
    aggregate = await get_grading_metrics_summary_aggregate(session, window=window)
    freshness_record = await get_latest_successful_grading_metrics_freshness(session)
    escalation_breakdown = await get_grading_metrics_escalation_breakdown(
        session,
        window=window,
        total_graded_customer_days=aggregate.total_graded_customer_days,
    )

    freshness = GradingMetricsFreshness(
        latest_successful_run_id=(
            None if freshness_record is None else freshness_record.run_id
        ),
        latest_successful_window_end_date=(
            None if freshness_record is None else freshness_record.target_end_date
        ),
        latest_successful_run_finished_at=(
            None if freshness_record is None else freshness_record.finished_at
        ),
    )

    return GradingMetricsSummaryResponse(
        date_window=GradingMetricsDateWindowSchema(
            start_date=aggregate.date_window.start_date,
            end_date=aggregate.date_window.end_date,
        ),
        total_graded_customer_days=aggregate.total_graded_customer_days,
        average_scores=aggregate.average_scores,
        outcome_rates=aggregate.outcome_rates,
        escalation_breakdown=escalation_breakdown,
        freshness=freshness,
    )


async def get_latest_successful_grading_metrics_freshness(
    session: AsyncSession,
) -> GradingMetricsFreshnessRecord | None:
    run = await session.scalar(build_latest_successful_grading_run_stmt())
    if run is None:
        return None
    return GradingMetricsFreshnessRecord(
        run_id=run.id,
        target_end_date=run.target_end_date,
        finished_at=run.finished_at,
    )


async def get_grading_metrics_escalation_breakdown(
    session: AsyncSession,
    *,
    window: GradingMetricsDateWindow,
    total_graded_customer_days: int,
) -> list[GradingMetricsEscalationBreakdownItem]:
    grades = build_summary_grades_stmt(window).subquery()
    result = await session.execute(
        select(
            grades.c.escalation_type.label("escalation_type"),
            func.count(grades.c.id).label("count"),
        )
        .where(grades.c.escalation_type.is_not(None))
        .group_by(grades.c.escalation_type)
    )
    counts_by_type = {
        str(row["escalation_type"]): int(row["count"] or 0)
        for row in result.mappings().all()
    }
    return [
        GradingMetricsEscalationBreakdownItem(
            escalation_type=escalation_type,
            count=counts_by_type.get(escalation_type, 0),
            share_pct=_to_pct(
                counts_by_type.get(escalation_type, 0),
                total_graded_customer_days,
            ),
        )
        for escalation_type in GRADING_ESCALATION_TYPE_VALUES
    ]


async def get_grading_score_trends(
    session: AsyncSession,
    query: GradingMetricsWindowQuery,
) -> GradingScoreTrendResponse:
    window = resolve_grading_metrics_window(query)
    grades = build_score_trend_grades_stmt(window).subquery()

    stmt = (
        select(
            grades.c.grade_date.label("date"),
            *[
                func.coalesce(
                    func.avg(getattr(grades.c, column_name)),
                    0.0,
                ).label(metric_key)
                for metric_key, column_name in GRADING_METRICS_SCORE_TO_COLUMN.items()
            ],
        )
        .group_by(grades.c.grade_date)
        .order_by(grades.c.grade_date)
    )
    rows = (await session.execute(stmt)).mappings().all()
    rows_by_date = {row["date"]: row for row in rows}

    points = [
        GradingScoreTrendPoint(
            date=point_date,
            **{
                metric_key: _to_score_value(
                    None if row is None else row[metric_key]
                )
                for metric_key in GRADING_METRICS_SCORE_TO_COLUMN
            },
        )
        for point_date in iter_grading_metrics_dates(window)
        for row in [rows_by_date.get(point_date)]
    ]

    return GradingScoreTrendResponse(
        date_window=GradingMetricsDateWindowSchema(
            start_date=window.start_date,
            end_date=window.end_date,
        ),
        points=points,
    )


async def get_grading_outcome_trends(
    *_args,
    **_kwargs,
) -> GradingOutcomeTrendResponse:
    raise NotImplementedError("Outcome trend aggregation is not implemented yet.")


async def get_grading_outcome_trends(
    session: AsyncSession,
    query: GradingMetricsWindowQuery,
) -> GradingOutcomeTrendResponse:
    window = resolve_grading_metrics_window(query)
    grades = build_outcome_trend_grades_stmt(window).subquery()

    stmt = (
        select(
            grades.c.grade_date.label("date"),
            func.count(grades.c.id).label("total_graded_customer_days"),
            func.sum(case((grades.c.resolution.is_(True), 1), else_=0)).label(
                "resolution_count"
            ),
            func.sum(case((grades.c.loop_detected.is_(True), 1), else_=0)).label(
                "loop_detected_count"
            ),
            func.sum(case((grades.c.user_relevancy.is_(False), 1), else_=0)).label(
                "non_genuine_count"
            ),
            func.sum(
                case((grades.c.escalation_occurred.is_(True), 1), else_=0)
            ).label("escalation_count"),
            func.sum(case((grades.c.escalation_type == "Failure", 1), else_=0)).label(
                "escalation_failure_count"
            ),
        )
        .group_by(grades.c.grade_date)
        .order_by(grades.c.grade_date)
    )
    rows = (await session.execute(stmt)).mappings().all()
    rows_by_date = {row["date"]: row for row in rows}

    points: list[GradingOutcomeTrendPoint] = []
    for point_date in iter_grading_metrics_dates(window):
        row = rows_by_date.get(point_date)
        total = int(0 if row is None else row["total_graded_customer_days"] or 0)
        points.append(
            GradingOutcomeTrendPoint(
                date=point_date,
                resolution_rate_pct=_to_score_value(
                    _to_pct(None if row is None else row["resolution_count"], total)
                ),
                loop_detected_rate_pct=_to_score_value(
                    _to_pct(None if row is None else row["loop_detected_count"], total)
                ),
                non_genuine_rate_pct=_to_score_value(
                    _to_pct(None if row is None else row["non_genuine_count"], total)
                ),
                escalation_rate_pct=_to_score_value(
                    _to_pct(None if row is None else row["escalation_count"], total)
                ),
                escalation_failure_rate_pct=_to_score_value(
                    _to_pct(
                        None if row is None else row["escalation_failure_count"],
                        total,
                    )
                ),
            )
        )

    return GradingOutcomeTrendResponse(
        date_window=GradingMetricsDateWindowSchema(
            start_date=window.start_date,
            end_date=window.end_date,
        ),
        points=points,
    )


async def get_intent_distribution(
    session: AsyncSession,
    query: GradingMetricsWindowQuery,
) -> GradingIntentDistributionResponse:
    window = resolve_grading_metrics_window(query)
    stmt = build_intent_distribution_grades_stmt(window)
    rows = (await session.scalars(stmt)).all()

    total = len(rows)
    counts: dict[str, int] = {code: 0 for code in INTENT_CODES}
    for row in rows:
        if row.intent_code and row.intent_code in counts:
            counts[row.intent_code] += 1

    items = [
        GradingIntentDistributionItem(
            intent_code=code,
            intent_label=INTENT_CODE_TO_LABEL[code],
            intent_category=INTENT_CODE_TO_CATEGORY[code],
            count=counts[code],
            share_pct=round(counts[code] / total * 100, 2) if total > 0 else 0.0,
        )
        for code in INTENT_CODES
    ]

    return GradingIntentDistributionResponse(
        date_window=query.date_window,
        total_graded_customer_days=total,
        items=items,
    )


async def get_intent_trend(
    session: AsyncSession,
    query: GradingMetricsIntentTrendQuery,
) -> GradingIntentTrendResponse:
    window = resolve_grading_metrics_window(query)
    all_dates = iter_grading_metrics_dates(window)
    requested_codes = list(query.intent_codes) if query.intent_codes else list(INTENT_CODES)

    stmt = build_intent_trend_grades_stmt(query)
    rows = (await session.scalars(stmt)).all()

    day_code_counts: dict[tuple[date, str], int] = {}
    for row in rows:
        if row.intent_code in requested_codes:
            key = (row.grade_date, row.intent_code)
            day_code_counts[key] = day_code_counts.get(key, 0) + 1

    series = [
        GradingIntentTrendSeries(
            intent_code=code,
            intent_label=INTENT_CODE_TO_LABEL[code],
            intent_category=INTENT_CODE_TO_CATEGORY[code],
            points=[
                GradingIntentTrendPoint(date=d, count=day_code_counts.get((d, code), 0))
                for d in all_dates
            ],
        )
        for code in requested_codes
    ]

    return GradingIntentTrendResponse(
        date_window=query.date_window,
        series=series,
    )
