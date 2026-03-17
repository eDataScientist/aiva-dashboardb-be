from __future__ import annotations

from datetime import date as calendar_date
from typing import Any

from sqlalchemy import Integer, Select, String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import INTENT_CODE_TO_CATEGORY, INTENT_CODE_TO_LABEL
from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.schemas.grading_dashboard_common import (
    GradingDashboardDailyTimelineQuery,
    GradingDashboardFreshness,
)
from app.schemas.grading_dashboard_daily_timeline import (
    GradingDashboardDailyTimelineHourlyBucket,
    GradingDashboardDailyTimelineHourSummary,
    GradingDashboardDailyTimelineResponse,
    GradingDashboardDailyTimelineScatterPoint,
    GradingDashboardDailyTimelineWorstPerformerRow,
)
from app.services.conversations import encode_conversation_key
from app.services.grading_extraction import (
    canonical_identity_type_expr,
    canonical_identity_value_expr,
    gst_grade_date_expr,
    gst_grade_hour_expr,
)
from app.services.grading_metrics import get_latest_successful_grading_metrics_freshness


def build_grading_dashboard_daily_timeline_stmt(
    *,
    target_date: calendar_date,
) -> Select[tuple[ConversationGrade]]:
    return select(ConversationGrade).where(ConversationGrade.grade_date == target_date)


async def get_grading_dashboard_daily_timeline(
    session: AsyncSession,
    query: GradingDashboardDailyTimelineQuery,
) -> GradingDashboardDailyTimelineResponse:
    target_date = query.target_date
    worst_performers_limit = query.worst_performers_limit

    grade_rows = (
        await session.scalars(
            build_grading_dashboard_daily_timeline_stmt(target_date=target_date)
        )
    ).all()

    hourly_buckets = await _build_daily_hourly_buckets(session, target_date)
    best_hour, worst_hour = _derive_best_worst_hour(hourly_buckets)

    scatter_points = _build_scatter_points(grade_rows)
    worst_performers = await _load_worst_performers(
        session, target_date, worst_performers_limit
    )

    freshness_record = await get_latest_successful_grading_metrics_freshness(session)
    freshness = GradingDashboardFreshness(
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

    return GradingDashboardDailyTimelineResponse(
        target_date=target_date,
        hourly_buckets=hourly_buckets,
        best_hour=best_hour,
        worst_hour=worst_hour,
        scatter_points=scatter_points,
        worst_performers=worst_performers,
        freshness=freshness,
    )


async def _build_daily_hourly_buckets(
    session: AsyncSession,
    target_date: calendar_date,
) -> list[GradingDashboardDailyTimelineHourlyBucket]:
    # Step 1 — inner subquery: canonical identity + raw created_at for same-day chats.
    # Variable capture ensures each expression object is compiled once (no GROUP BY param mismatch).
    identity_type_expr = canonical_identity_type_expr()
    identity_value_expr = canonical_identity_value_expr()
    grade_date_expr = gst_grade_date_expr()

    chat_rows_sq = (
        select(
            identity_type_expr.label("identity_type"),
            identity_value_expr.label("conversation_identity"),
            ChatMessage.created_at.label("created_at"),
        )
        .where(identity_value_expr.is_not(None))
        .where(grade_date_expr == target_date)
    ).subquery("chat_rows")

    # Step 2 — outer query: MIN(created_at) per canonical customer-day.
    # GROUP BY on plain subquery column refs — no complex expression matching issues.
    first_msg_sq = (
        select(
            chat_rows_sq.c.identity_type,
            chat_rows_sq.c.conversation_identity,
            func.min(chat_rows_sq.c.created_at).label("first_msg_at"),
        )
        .group_by(
            chat_rows_sq.c.identity_type,
            chat_rows_sq.c.conversation_identity,
        )
    ).subquery("first_messages")

    first_msg_hour_stmt = select(
        first_msg_sq.c.identity_type,
        first_msg_sq.c.conversation_identity,
        gst_grade_hour_expr(first_msg_sq.c.first_msg_at).label("first_msg_hour"),
    )

    msg_rows = (await session.execute(first_msg_hour_stmt)).mappings().all()
    first_msg_hour_by_identity: dict[tuple[str, str], int] = {
        (str(row["identity_type"]), str(row["conversation_identity"])): int(
            row["first_msg_hour"]
        )
        for row in msg_rows
        if row["first_msg_hour"] is not None
    }

    # Step 3 — load grade rows with canonical identity and merge.
    grade_rows = (
        await session.scalars(
            select(ConversationGrade)
            .where(ConversationGrade.grade_date == target_date)
            .where(ConversationGrade.identity_type.is_not(None))
            .where(ConversationGrade.conversation_identity.is_not(None))
        )
    ).all()

    hour_volumes = [0] * 24
    hour_resolutions = [0] * 24
    for grade in grade_rows:
        key = (str(grade.identity_type), str(grade.conversation_identity))
        hour = first_msg_hour_by_identity.get(key)
        if hour is None:
            continue
        if 0 <= hour <= 23:
            hour_volumes[hour] += 1
            if grade.resolution is True:
                hour_resolutions[hour] += 1

    return [
        GradingDashboardDailyTimelineHourlyBucket(
            hour=h,
            conversation_volume=hour_volumes[h],
            resolution_rate_pct=_to_pct(hour_resolutions[h], hour_volumes[h]),
        )
        for h in range(24)
    ]


def _derive_best_worst_hour(
    hourly_buckets: list[GradingDashboardDailyTimelineHourlyBucket],
) -> tuple[
    GradingDashboardDailyTimelineHourSummary | None,
    GradingDashboardDailyTimelineHourSummary | None,
]:
    non_empty = [b for b in hourly_buckets if b.conversation_volume > 0]
    if not non_empty:
        return None, None

    best = max(non_empty, key=lambda b: (b.resolution_rate_pct, b.conversation_volume, -b.hour))
    worst = min(non_empty, key=lambda b: (b.resolution_rate_pct, -b.conversation_volume, b.hour))

    return (
        GradingDashboardDailyTimelineHourSummary(
            hour=best.hour,
            conversation_volume=best.conversation_volume,
            resolution_rate_pct=best.resolution_rate_pct,
        ),
        GradingDashboardDailyTimelineHourSummary(
            hour=worst.hour,
            conversation_volume=worst.conversation_volume,
            resolution_rate_pct=worst.resolution_rate_pct,
        ),
    )


def _build_scatter_points(
    grade_rows: Any,
) -> list[GradingDashboardDailyTimelineScatterPoint]:
    points: list[GradingDashboardDailyTimelineScatterPoint] = []
    for grade in grade_rows:
        if grade.satisfaction_score is None or grade.frustration_score is None:
            continue
        conversation_key = _resolve_conversation_key(grade)
        if conversation_key is None:
            continue
        points.append(
            GradingDashboardDailyTimelineScatterPoint(
                grade_id=grade.id,
                conversation_key=conversation_key,
                satisfaction_score=float(grade.satisfaction_score),
                frustration_score=float(grade.frustration_score),
                resolution=grade.resolution,
                loop_detected=grade.loop_detected,
            )
        )
    return points


async def _load_worst_performers(
    session: AsyncSession,
    target_date: calendar_date,
    limit: int,
) -> list[GradingDashboardDailyTimelineWorstPerformerRow]:
    contact_label_expr = _build_contact_label_correlated_subquery().label("contact_label")

    ai_score_sum = (
        cast(ConversationGrade.relevancy_score, Integer)
        + cast(ConversationGrade.accuracy_score, Integer)
        + cast(ConversationGrade.completeness_score, Integer)
        + cast(ConversationGrade.clarity_score, Integer)
        + cast(ConversationGrade.tone_score, Integer)
    )

    stmt = (
        select(ConversationGrade, contact_label_expr, ai_score_sum.label("composite_sum"))
        .where(ConversationGrade.grade_date == target_date)
        .where(ConversationGrade.relevancy_score.is_not(None))
        .where(ConversationGrade.accuracy_score.is_not(None))
        .where(ConversationGrade.completeness_score.is_not(None))
        .where(ConversationGrade.clarity_score.is_not(None))
        .where(ConversationGrade.tone_score.is_not(None))
        .where(ConversationGrade.satisfaction_score.is_not(None))
        .where(ConversationGrade.frustration_score.is_not(None))
        .order_by(ai_score_sum.asc(), ConversationGrade.id.asc())
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    performers: list[GradingDashboardDailyTimelineWorstPerformerRow] = []

    for grade, contact_label_raw, _composite in rows:
        conversation_key = _resolve_conversation_key(grade)
        if conversation_key is None:
            continue
        intent_code = _resolve_intent_code(grade.intent_code)
        performers.append(
            GradingDashboardDailyTimelineWorstPerformerRow(
                grade_id=grade.id,
                conversation_key=conversation_key,
                contact_label=_strip_or_none(contact_label_raw),
                relevancy_score=grade.relevancy_score,
                accuracy_score=grade.accuracy_score,
                completeness_score=grade.completeness_score,
                clarity_score=grade.clarity_score,
                tone_score=grade.tone_score,
                satisfaction_score=grade.satisfaction_score,
                frustration_score=grade.frustration_score,
                resolution=grade.resolution,
                escalation_type=grade.escalation_type,
                intent_code=intent_code,
                intent_label=(
                    INTENT_CODE_TO_LABEL[intent_code] if intent_code is not None else None
                ),
                intent_category=(
                    INTENT_CODE_TO_CATEGORY[intent_code] if intent_code is not None else None
                ),
            )
        )
    return performers


def _build_contact_label_correlated_subquery() -> Any:
    contact_name_expr = func.nullif(
        func.btrim(cast(ChatMessage.customer_name, String())), ""
    )
    return (
        select(contact_name_expr)
        .where(
            canonical_identity_type_expr() == ConversationGrade.identity_type,
            canonical_identity_value_expr() == ConversationGrade.conversation_identity,
            gst_grade_date_expr() == ConversationGrade.grade_date,
        )
        .order_by(
            case((contact_name_expr.is_(None), 1), else_=0),
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .correlate(ConversationGrade)
        .limit(1)
        .scalar_subquery()
    )


def _to_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _resolve_conversation_key(grade: ConversationGrade) -> str | None:
    conversation_identity = _strip_or_none(grade.conversation_identity)
    if conversation_identity is not None:
        return encode_conversation_key(conversation_identity)
    phone_number = _strip_or_none(grade.phone_number)
    if phone_number is None:
        return None
    return encode_conversation_key(phone_number)


def _resolve_intent_code(intent_code: str | None) -> str | None:
    normalized = _strip_or_none(intent_code)
    if normalized is None:
        return None
    canonical = normalized.lower()
    return canonical if canonical in INTENT_CODE_TO_LABEL else None


def _strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
