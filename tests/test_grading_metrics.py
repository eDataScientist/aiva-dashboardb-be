from __future__ import annotations

from datetime import date, datetime

import pytest

from app.core.constants import (
    GRADING_DEFAULT_MODEL,
    GRADING_DEFAULT_PROMPT_VERSION,
    INTENT_CODES,
    INTENT_CODE_TO_CATEGORY,
    INTENT_CODE_TO_LABEL,
)
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun
from app.schemas.grading_metrics import (
    GradingMetricsIntentTrendQuery,
    GradingMetricsWindowQuery,
)
from app.schemas.grading_runs import (
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)
from app.services.grading_metrics import (
    GradingMetricsDateWindow,
    get_grading_metrics_summary_aggregate,
    get_grading_metrics_summary,
    get_grading_outcome_trends,
    get_grading_score_trends,
    get_intent_distribution,
    get_intent_trend,
)


async def _persist_grade(
    db_session,
    *,
    phone_number: str,
    grade_date: date,
    relevancy_score: int,
    accuracy_score: int,
    completeness_score: int,
    clarity_score: int,
    tone_score: int,
    repetition_score: int,
    satisfaction_score: int,
    frustration_score: int,
    resolution: bool | None = None,
    loop_detected: bool | None = None,
    user_relevancy: bool | None = None,
    escalation_occurred: bool | None = None,
    escalation_type: str | None = None,
) -> ConversationGrade:
    grade = ConversationGrade(
        phone_number=phone_number,
        grade_date=grade_date,
        identity_type=IdentityType.PHONE,
        conversation_identity=phone_number,
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        relevancy_score=relevancy_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        clarity_score=clarity_score,
        tone_score=tone_score,
        repetition_score=repetition_score,
        satisfaction_score=satisfaction_score,
        frustration_score=frustration_score,
        resolution=resolution,
        loop_detected=loop_detected,
        user_relevancy=user_relevancy,
        escalation_occurred=escalation_occurred,
        escalation_type=escalation_type,
    )
    db_session.add(grade)
    await db_session.flush()
    return grade


async def _persist_run(
    db_session,
    *,
    status: str,
    target_end_date: date,
    created_at: datetime,
    finished_at: datetime | None = None,
) -> GradingRun:
    run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.MANUAL.value,
        run_mode=GradingRunModeSchema.BACKFILL.value,
        status=status,
        target_start_date=target_end_date,
        target_end_date=target_end_date,
        rerun_existing=False,
        provider="mock",
        model=GRADING_DEFAULT_MODEL,
        prompt_version=GRADING_DEFAULT_PROMPT_VERSION,
        created_at=created_at,
        updated_at=created_at,
        finished_at=finished_at,
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest.mark.asyncio
async def test_get_grading_score_trends_zero_fills_sparse_window(db_session) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000001",
        grade_date=date(2026, 3, 9),
        relevancy_score=8,
        accuracy_score=6,
        completeness_score=7,
        clarity_score=8,
        tone_score=9,
        repetition_score=6,
        satisfaction_score=7,
        frustration_score=2,
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000002",
        grade_date=date(2026, 3, 9),
        relevancy_score=6,
        accuracy_score=8,
        completeness_score=9,
        clarity_score=6,
        tone_score=7,
        repetition_score=8,
        satisfaction_score=9,
        frustration_score=4,
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000003",
        grade_date=date(2026, 3, 11),
        relevancy_score=9,
        accuracy_score=9,
        completeness_score=8,
        clarity_score=7,
        tone_score=8,
        repetition_score=9,
        satisfaction_score=8,
        frustration_score=1,
    )

    response = await get_grading_score_trends(
        db_session,
        GradingMetricsWindowQuery(
            start_date=date(2026, 3, 9),
            end_date=date(2026, 3, 11),
        ),
    )

    assert [point.date for point in response.points] == [
        date(2026, 3, 9),
        date(2026, 3, 10),
        date(2026, 3, 11),
    ]
    assert response.points[0].relevancy == 7.0
    assert response.points[0].accuracy == 7.0
    assert response.points[0].completeness == 8.0
    assert response.points[0].clarity == 7.0
    assert response.points[0].tone == 8.0
    assert response.points[0].repetition == 7.0
    assert response.points[0].satisfaction == 8.0
    assert response.points[0].frustration == 3.0
    assert response.points[1].relevancy == 0.0
    assert response.points[1].accuracy == 0.0
    assert response.points[1].completeness == 0.0
    assert response.points[1].clarity == 0.0
    assert response.points[1].tone == 0.0
    assert response.points[1].repetition == 0.0
    assert response.points[1].satisfaction == 0.0
    assert response.points[1].frustration == 0.0
    assert response.points[2].relevancy == 9.0
    assert response.points[2].accuracy == 9.0
    assert response.points[2].completeness == 8.0
    assert response.points[2].clarity == 7.0
    assert response.points[2].tone == 8.0
    assert response.points[2].repetition == 9.0
    assert response.points[2].satisfaction == 8.0
    assert response.points[2].frustration == 1.0


@pytest.mark.asyncio
async def test_get_grading_outcome_trends_uses_daily_denominators_and_zero_fill(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000021",
        grade_date=date(2026, 3, 9),
        relevancy_score=8,
        accuracy_score=8,
        completeness_score=8,
        clarity_score=8,
        tone_score=8,
        repetition_score=8,
        satisfaction_score=8,
        frustration_score=2,
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=False,
        escalation_type="None",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000022",
        grade_date=date(2026, 3, 9),
        relevancy_score=4,
        accuracy_score=5,
        completeness_score=6,
        clarity_score=5,
        tone_score=6,
        repetition_score=4,
        satisfaction_score=3,
        frustration_score=7,
        resolution=False,
        loop_detected=True,
        user_relevancy=False,
        escalation_occurred=True,
        escalation_type="Failure",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000023",
        grade_date=date(2026, 3, 11),
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        repetition_score=7,
        satisfaction_score=7,
        frustration_score=3,
        resolution=True,
        loop_detected=False,
        user_relevancy=False,
        escalation_occurred=False,
        escalation_type="None",
    )

    response = await get_grading_outcome_trends(
        db_session,
        GradingMetricsWindowQuery(
            start_date=date(2026, 3, 9),
            end_date=date(2026, 3, 11),
        ),
    )

    assert [point.date for point in response.points] == [
        date(2026, 3, 9),
        date(2026, 3, 10),
        date(2026, 3, 11),
    ]
    assert response.points[0].resolution_rate_pct == 50.0
    assert response.points[0].loop_detected_rate_pct == 50.0
    assert response.points[0].non_genuine_rate_pct == 50.0
    assert response.points[0].escalation_rate_pct == 50.0
    assert response.points[0].escalation_failure_rate_pct == 50.0
    assert response.points[1].resolution_rate_pct == 0.0
    assert response.points[1].loop_detected_rate_pct == 0.0
    assert response.points[1].non_genuine_rate_pct == 0.0
    assert response.points[1].escalation_rate_pct == 0.0
    assert response.points[1].escalation_failure_rate_pct == 0.0
    assert response.points[2].resolution_rate_pct == 100.0
    assert response.points[2].loop_detected_rate_pct == 0.0
    assert response.points[2].non_genuine_rate_pct == 100.0
    assert response.points[2].escalation_rate_pct == 0.0
    assert response.points[2].escalation_failure_rate_pct == 0.0


@pytest.mark.asyncio
async def test_grading_trends_return_zero_filled_points_for_empty_window(
    db_session,
) -> None:
    window = GradingMetricsWindowQuery(
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 7),
    )

    score_response = await get_grading_score_trends(db_session, window)
    outcome_response = await get_grading_outcome_trends(db_session, window)

    assert [point.date for point in score_response.points] == [
        date(2026, 3, 5),
        date(2026, 3, 6),
        date(2026, 3, 7),
    ]
    for point in score_response.points:
        assert point.relevancy == 0.0
        assert point.accuracy == 0.0
        assert point.completeness == 0.0
        assert point.clarity == 0.0
        assert point.tone == 0.0
        assert point.repetition == 0.0
        assert point.satisfaction == 0.0
        assert point.frustration == 0.0

    assert [point.date for point in outcome_response.points] == [
        date(2026, 3, 5),
        date(2026, 3, 6),
        date(2026, 3, 7),
    ]
    for point in outcome_response.points:
        assert point.resolution_rate_pct == 0.0
        assert point.loop_detected_rate_pct == 0.0
        assert point.non_genuine_rate_pct == 0.0
        assert point.escalation_rate_pct == 0.0
        assert point.escalation_failure_rate_pct == 0.0


@pytest.mark.asyncio
async def test_get_grading_outcome_trends_rounds_fractional_daily_percentages(
    db_session,
) -> None:
    target_date = date(2026, 3, 8)
    await _persist_grade(
        db_session,
        phone_number="+971500000031",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        repetition_score=7,
        satisfaction_score=7,
        frustration_score=3,
        resolution=True,
        loop_detected=True,
        user_relevancy=True,
        escalation_occurred=True,
        escalation_type="Failure",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000032",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        repetition_score=7,
        satisfaction_score=7,
        frustration_score=3,
        resolution=False,
        loop_detected=False,
        user_relevancy=False,
        escalation_occurred=False,
        escalation_type="None",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000033",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        repetition_score=7,
        satisfaction_score=7,
        frustration_score=3,
        resolution=False,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=False,
        escalation_type="None",
    )

    response = await get_grading_outcome_trends(
        db_session,
        GradingMetricsWindowQuery(
            start_date=target_date,
            end_date=target_date,
        ),
    )

    assert len(response.points) == 1
    point = response.points[0]
    assert point.resolution_rate_pct == 33.33
    assert point.loop_detected_rate_pct == 33.33
    assert point.non_genuine_rate_pct == 33.33
    assert point.escalation_rate_pct == 33.33
    assert point.escalation_failure_rate_pct == 33.33


@pytest.mark.asyncio
async def test_get_grading_metrics_summary_aggregate_returns_selected_window_metrics(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000011",
        grade_date=date(2026, 3, 10),
        relevancy_score=8,
        accuracy_score=7,
        completeness_score=9,
        clarity_score=8,
        tone_score=9,
        repetition_score=6,
        satisfaction_score=8,
        frustration_score=2,
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=False,
        escalation_type="None",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000012",
        grade_date=date(2026, 3, 11),
        relevancy_score=4,
        accuracy_score=5,
        completeness_score=6,
        clarity_score=7,
        tone_score=8,
        repetition_score=2,
        satisfaction_score=4,
        frustration_score=6,
        resolution=False,
        loop_detected=True,
        user_relevancy=False,
        escalation_occurred=True,
        escalation_type="Failure",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000013",
        grade_date=date(2026, 3, 12),
        relevancy_score=10,
        accuracy_score=10,
        completeness_score=10,
        clarity_score=10,
        tone_score=10,
        repetition_score=10,
        satisfaction_score=10,
        frustration_score=1,
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=False,
        escalation_type="None",
    )

    summary = await get_grading_metrics_summary_aggregate(
        db_session,
        window=GradingMetricsDateWindow(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
        ),
    )

    assert summary.total_graded_customer_days == 2
    assert summary.average_scores.relevancy == pytest.approx(6.0)
    assert summary.average_scores.accuracy == pytest.approx(6.0)
    assert summary.average_scores.completeness == pytest.approx(7.5)
    assert summary.average_scores.clarity == pytest.approx(7.5)
    assert summary.average_scores.tone == pytest.approx(8.5)
    assert summary.average_scores.repetition == pytest.approx(4.0)
    assert summary.average_scores.satisfaction == pytest.approx(6.0)
    assert summary.average_scores.frustration == pytest.approx(4.0)
    assert summary.outcome_rates.resolution_rate_pct == pytest.approx(50.0)
    assert summary.outcome_rates.loop_detected_rate_pct == pytest.approx(50.0)
    assert summary.outcome_rates.non_genuine_rate_pct == pytest.approx(50.0)
    assert summary.outcome_rates.escalation_rate_pct == pytest.approx(50.0)
    assert summary.outcome_rates.escalation_failure_rate_pct == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_get_grading_metrics_summary_aggregate_returns_zeroes_for_empty_windows(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000014",
        grade_date=date(2026, 3, 12),
        relevancy_score=8,
        accuracy_score=8,
        completeness_score=8,
        clarity_score=8,
        tone_score=8,
        repetition_score=8,
        satisfaction_score=8,
        frustration_score=2,
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=False,
        escalation_type="None",
    )

    summary = await get_grading_metrics_summary_aggregate(
        db_session,
        window=GradingMetricsDateWindow(
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 2),
        ),
    )

    assert summary.total_graded_customer_days == 0
    assert summary.average_scores.relevancy == 0.0
    assert summary.average_scores.accuracy == 0.0
    assert summary.average_scores.completeness == 0.0
    assert summary.average_scores.clarity == 0.0
    assert summary.average_scores.tone == 0.0
    assert summary.average_scores.repetition == 0.0
    assert summary.average_scores.satisfaction == 0.0
    assert summary.average_scores.frustration == 0.0
    assert summary.outcome_rates.resolution_rate_pct == 0.0
    assert summary.outcome_rates.loop_detected_rate_pct == 0.0
    assert summary.outcome_rates.non_genuine_rate_pct == 0.0
    assert summary.outcome_rates.escalation_rate_pct == 0.0
    assert summary.outcome_rates.escalation_failure_rate_pct == 0.0


@pytest.mark.asyncio
async def test_get_grading_metrics_summary_includes_escalation_breakdown_and_latest_success(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000101",
        grade_date=date(2026, 3, 10),
        relevancy_score=8,
        accuracy_score=7,
        completeness_score=9,
        clarity_score=8,
        tone_score=9,
        repetition_score=6,
        satisfaction_score=8,
        frustration_score=2,
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=True,
        escalation_type="Failure",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000102",
        grade_date=date(2026, 3, 11),
        relevancy_score=6,
        accuracy_score=6,
        completeness_score=6,
        clarity_score=6,
        tone_score=6,
        repetition_score=6,
        satisfaction_score=6,
        frustration_score=4,
        resolution=False,
        loop_detected=True,
        user_relevancy=False,
        escalation_occurred=False,
        escalation_type="None",
    )
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 10),
        created_at=datetime(2026, 3, 12, 8, 0, 0),
        finished_at=datetime(2026, 3, 12, 8, 30, 0),
    )
    newer_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED_WITH_FAILURES.value,
        target_end_date=date(2026, 3, 11),
        created_at=datetime(2026, 3, 12, 9, 0, 0),
        finished_at=datetime(2026, 3, 12, 9, 30, 0),
    )

    response = await get_grading_metrics_summary(
        db_session,
        GradingMetricsWindowQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.total_graded_customer_days == 2
    assert [item.escalation_type.value for item in response.escalation_breakdown] == [
        "Natural",
        "Failure",
        "None",
    ]
    assert [item.count for item in response.escalation_breakdown] == [0, 1, 1]
    assert response.escalation_breakdown[0].share_pct == 0.0
    assert response.escalation_breakdown[1].share_pct == pytest.approx(50.0)
    assert response.escalation_breakdown[2].share_pct == pytest.approx(50.0)
    assert response.freshness.latest_successful_run_id == newer_run.id
    assert response.freshness.latest_successful_window_end_date == date(2026, 3, 11)
    assert response.freshness.latest_successful_run_finished_at == datetime(
        2026,
        3,
        12,
        9,
        30,
        0,
    )


@pytest.mark.asyncio
async def test_get_grading_metrics_summary_ignores_failed_latest_run_for_freshness(
    db_session,
) -> None:
    successful_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 9),
        created_at=datetime(2026, 3, 12, 8, 0, 0),
        finished_at=datetime(2026, 3, 12, 8, 15, 0),
    )
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.FAILED.value,
        target_end_date=date(2026, 3, 11),
        created_at=datetime(2026, 3, 12, 9, 0, 0),
        finished_at=datetime(2026, 3, 12, 9, 30, 0),
    )

    response = await get_grading_metrics_summary(
        db_session,
        GradingMetricsWindowQuery(
            start_date=date(2026, 3, 9),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.freshness.latest_successful_run_id == successful_run.id
    assert response.freshness.latest_successful_window_end_date == date(2026, 3, 9)
    assert response.freshness.latest_successful_run_finished_at == datetime(
        2026,
        3,
        12,
        8,
        15,
        0,
    )


@pytest.mark.asyncio
async def test_get_grading_metrics_summary_returns_null_freshness_without_successful_runs(
    db_session,
) -> None:
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.FAILED.value,
        target_end_date=date(2026, 3, 11),
        created_at=datetime(2026, 3, 12, 9, 0, 0),
        finished_at=datetime(2026, 3, 12, 9, 30, 0),
    )

    response = await get_grading_metrics_summary(
        db_session,
        GradingMetricsWindowQuery(
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 2),
        ),
    )

    assert response.total_graded_customer_days == 0
    assert [item.count for item in response.escalation_breakdown] == [0, 0, 0]
    assert [item.share_pct for item in response.escalation_breakdown] == [0.0, 0.0, 0.0]
    assert response.freshness.latest_successful_run_id is None
    assert response.freshness.latest_successful_window_end_date is None
    assert response.freshness.latest_successful_run_finished_at is None


# ---------------------------------------------------------------------------
# P2.5.12 / P2.5.14 - get_intent_distribution
# ---------------------------------------------------------------------------


def _intent_grade(*, grade_date: date, intent_code: str | None = None) -> ConversationGrade:
    return ConversationGrade(grade_date=grade_date, intent_code=intent_code)


async def _seed_intents(db_session, *rows: ConversationGrade) -> None:
    db_session.add_all(list(rows))
    await db_session.commit()


@pytest.mark.asyncio
async def test_intent_distribution_returns_all_canonical_codes_with_correct_counts(
    db_session,
) -> None:
    d = date(2026, 1, 10)
    await _seed_intents(
        db_session,
        _intent_grade(grade_date=d, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d, intent_code="claims_submission"),
        _intent_grade(grade_date=d, intent_code="claims_submission"),
        _intent_grade(grade_date=d, intent_code="payment_inquiry"),
    )

    result = await get_intent_distribution(
        db_session,
        GradingMetricsWindowQuery.model_construct(start_date=d, end_date=d),
    )

    assert result.total_graded_customer_days == 6
    assert len(result.items) == len(INTENT_CODES)

    by_code = {item.intent_code: item for item in result.items}
    assert by_code["policy_inquiry"].count == 3
    assert by_code["policy_inquiry"].share_pct == 50.0
    assert by_code["claims_submission"].count == 2
    assert by_code["claims_submission"].share_pct == round(2 / 6 * 100, 2)
    assert by_code["payment_inquiry"].count == 1
    assert by_code["payment_inquiry"].share_pct == round(1 / 6 * 100, 2)
    for code in INTENT_CODES:
        if code not in ("policy_inquiry", "claims_submission", "payment_inquiry"):
            assert by_code[code].count == 0
            assert by_code[code].share_pct == 0.0


@pytest.mark.asyncio
async def test_intent_distribution_carries_canonical_taxonomy_metadata(
    db_session,
) -> None:
    d = date(2026, 1, 11)
    await _seed_intents(db_session, _intent_grade(grade_date=d, intent_code="claims_dispute"))

    result = await get_intent_distribution(
        db_session,
        GradingMetricsWindowQuery.model_construct(start_date=d, end_date=d),
    )

    by_code = {item.intent_code: item for item in result.items}
    item = by_code["claims_dispute"]
    assert item.intent_label == INTENT_CODE_TO_LABEL["claims_dispute"]
    assert item.intent_category == INTENT_CODE_TO_CATEGORY["claims_dispute"]


@pytest.mark.asyncio
async def test_intent_distribution_empty_window_returns_all_codes_zeroed(
    db_session,
) -> None:
    d = date(2026, 1, 12)
    result = await get_intent_distribution(
        db_session,
        GradingMetricsWindowQuery.model_construct(start_date=d, end_date=d),
    )

    assert result.total_graded_customer_days == 0
    assert len(result.items) == len(INTENT_CODES)
    for item in result.items:
        assert item.count == 0
        assert item.share_pct == 0.0


@pytest.mark.asyncio
async def test_intent_distribution_null_intent_code_rows_count_in_total_but_not_items(
    db_session,
) -> None:
    d = date(2026, 1, 13)
    await _seed_intents(
        db_session,
        _intent_grade(grade_date=d, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d, intent_code=None),
    )

    result = await get_intent_distribution(
        db_session,
        GradingMetricsWindowQuery.model_construct(start_date=d, end_date=d),
    )

    assert result.total_graded_customer_days == 3
    by_code = {item.intent_code: item for item in result.items}
    assert by_code["policy_inquiry"].count == 2
    assert by_code["policy_inquiry"].share_pct == round(2 / 3 * 100, 2)
    for code in INTENT_CODES:
        if code != "policy_inquiry":
            assert by_code[code].count == 0


@pytest.mark.asyncio
async def test_intent_distribution_date_boundary_excludes_out_of_window_rows(
    db_session,
) -> None:
    d_in = date(2026, 1, 14)
    d_out = date(2026, 1, 15)
    await _seed_intents(
        db_session,
        _intent_grade(grade_date=d_in, intent_code="complaint"),
        _intent_grade(grade_date=d_out, intent_code="complaint"),
    )

    result = await get_intent_distribution(
        db_session,
        GradingMetricsWindowQuery.model_construct(start_date=d_in, end_date=d_in),
    )

    assert result.total_graded_customer_days == 1
    by_code = {item.intent_code: item for item in result.items}
    assert by_code["complaint"].count == 1


# ---------------------------------------------------------------------------
# P2.5.13 / P2.5.14 - get_intent_trend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intent_trend_all_codes_returned_with_daily_zero_fill(
    db_session,
) -> None:
    d1 = date(2026, 1, 16)
    d2 = date(2026, 1, 17)
    d3 = date(2026, 1, 18)
    await _seed_intents(
        db_session,
        _intent_grade(grade_date=d1, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d1, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d1, intent_code="claims_submission"),
        _intent_grade(grade_date=d2, intent_code="policy_inquiry"),
    )

    result = await get_intent_trend(
        db_session,
        GradingMetricsIntentTrendQuery.model_construct(
            start_date=d1, end_date=d3, intent_codes=[],
        ),
    )

    assert len(result.series) == len(INTENT_CODES)
    by_code = {s.intent_code: s for s in result.series}

    pi = by_code["policy_inquiry"]
    assert len(pi.points) == 3
    counts = {p.date: p.count for p in pi.points}
    assert counts[d1] == 2
    assert counts[d2] == 1
    assert counts[d3] == 0

    cs = by_code["claims_submission"]
    cs_counts = {p.date: p.count for p in cs.points}
    assert cs_counts[d1] == 1
    assert cs_counts[d2] == 0
    assert cs_counts[d3] == 0

    for code in INTENT_CODES:
        if code not in ("policy_inquiry", "claims_submission"):
            for pt in by_code[code].points:
                assert pt.count == 0


@pytest.mark.asyncio
async def test_intent_trend_filtered_codes_returns_only_requested_series(
    db_session,
) -> None:
    d1 = date(2026, 1, 19)
    d2 = date(2026, 1, 20)
    await _seed_intents(
        db_session,
        _intent_grade(grade_date=d1, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d1, intent_code="policy_inquiry"),
        _intent_grade(grade_date=d1, intent_code="payment_inquiry"),
        _intent_grade(grade_date=d1, intent_code="complaint"),
    )

    result = await get_intent_trend(
        db_session,
        GradingMetricsIntentTrendQuery.model_construct(
            start_date=d1,
            end_date=d2,
            intent_codes=["policy_inquiry", "payment_inquiry"],
        ),
    )

    assert len(result.series) == 2
    codes = {s.intent_code for s in result.series}
    assert codes == {"policy_inquiry", "payment_inquiry"}

    by_code = {s.intent_code: s for s in result.series}
    pi_counts = {p.date: p.count for p in by_code["policy_inquiry"].points}
    assert pi_counts[d1] == 2
    assert pi_counts[d2] == 0

    pay_counts = {p.date: p.count for p in by_code["payment_inquiry"].points}
    assert pay_counts[d1] == 1
    assert pay_counts[d2] == 0


@pytest.mark.asyncio
async def test_intent_trend_filtered_code_with_no_matching_rows_is_zero_filled(
    db_session,
) -> None:
    d1 = date(2026, 1, 21)
    d2 = date(2026, 1, 22)
    await _seed_intents(db_session, _intent_grade(grade_date=d1, intent_code="policy_inquiry"))

    result = await get_intent_trend(
        db_session,
        GradingMetricsIntentTrendQuery.model_construct(
            start_date=d1,
            end_date=d2,
            intent_codes=["claims_dispute"],
        ),
    )

    assert len(result.series) == 1
    series = result.series[0]
    assert series.intent_code == "claims_dispute"
    assert len(series.points) == 2
    for pt in series.points:
        assert pt.count == 0


@pytest.mark.asyncio
async def test_intent_trend_carries_canonical_metadata_per_series(
    db_session,
) -> None:
    d = date(2026, 1, 23)
    result = await get_intent_trend(
        db_session,
        GradingMetricsIntentTrendQuery.model_construct(
            start_date=d,
            end_date=d,
            intent_codes=["escalation_request"],
        ),
    )

    assert len(result.series) == 1
    series = result.series[0]
    assert series.intent_code == "escalation_request"
    assert series.intent_label == INTENT_CODE_TO_LABEL["escalation_request"]
    assert series.intent_category == INTENT_CODE_TO_CATEGORY["escalation_request"]


@pytest.mark.asyncio
async def test_intent_trend_empty_window_all_codes_returns_zero_filled_single_point(
    db_session,
) -> None:
    d = date(2026, 1, 24)
    result = await get_intent_trend(
        db_session,
        GradingMetricsIntentTrendQuery.model_construct(
            start_date=d, end_date=d, intent_codes=[],
        ),
    )

    assert len(result.series) == len(INTENT_CODES)
    for series in result.series:
        assert len(series.points) == 1
        assert series.points[0].date == d
        assert series.points[0].count == 0
