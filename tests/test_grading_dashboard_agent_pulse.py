from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun
from app.schemas.grading_dashboard_common import GradingDashboardWindowQuery
from app.schemas.grading_runs import (
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)
from app.services.grading_dashboard_agent_pulse import (
    get_grading_dashboard_agent_pulse,
)


async def _persist_grade(
    db_session,
    *,
    phone_number: str,
    grade_date: date,
    intent_code: str,
    relevancy_score: int,
    accuracy_score: int,
    completeness_score: int,
    clarity_score: int,
    tone_score: int,
    repetition_score: int,
    satisfaction_score: int,
    frustration_score: int,
    resolution: bool,
    loop_detected: bool,
    user_relevancy: bool,
    escalation_occurred: bool,
    escalation_type: str,
) -> ConversationGrade:
    grade = ConversationGrade(
        phone_number=phone_number,
        grade_date=grade_date,
        identity_type=IdentityType.PHONE,
        conversation_identity=phone_number,
        intent_code=intent_code,
        intent_label=intent_code.replace("_", " ").title(),
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
        model="mock-grade-v1",
        prompt_version="v1",
        created_at=created_at,
        updated_at=created_at,
        finished_at=finished_at,
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest.mark.asyncio
async def test_get_grading_dashboard_agent_pulse_returns_core_aggregates(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000101",
        grade_date=date(2026, 3, 10),
        intent_code="policy_inquiry",
        relevancy_score=8,
        accuracy_score=6,
        completeness_score=7,
        clarity_score=9,
        tone_score=10,
        repetition_score=4,
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
        phone_number="+971500000102",
        grade_date=date(2026, 3, 11),
        intent_code="claims_submission",
        relevancy_score=4,
        accuracy_score=5,
        completeness_score=6,
        clarity_score=7,
        tone_score=8,
        repetition_score=8,
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
        phone_number="+971500000103",
        grade_date=date(2026, 3, 11),
        intent_code="policy_inquiry",
        relevancy_score=7,
        accuracy_score=8,
        completeness_score=9,
        clarity_score=6,
        tone_score=7,
        repetition_score=5,
        satisfaction_score=7,
        frustration_score=3,
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=True,
        escalation_type="Natural",
    )

    response = await get_grading_dashboard_agent_pulse(
        db_session,
        GradingDashboardWindowQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.date_window.start_date == date(2026, 3, 10)
    assert response.date_window.end_date == date(2026, 3, 11)
    assert response.total_graded_customer_days == 3
    assert response.overall_composite_score == pytest.approx(7.13, abs=0.01)
    assert response.dimension_averages.relevancy == pytest.approx(6.33, abs=0.01)
    assert response.dimension_averages.accuracy == pytest.approx(6.33, abs=0.01)
    assert response.dimension_averages.completeness == pytest.approx(7.33, abs=0.01)
    assert response.dimension_averages.clarity == pytest.approx(7.33, abs=0.01)
    assert response.dimension_averages.tone == pytest.approx(8.33, abs=0.01)
    assert response.health.resolution_rate_pct == pytest.approx(66.67, abs=0.01)
    assert response.health.avg_repetition_score == pytest.approx(5.67, abs=0.01)
    assert response.health.loop_detected_rate_pct == pytest.approx(33.33, abs=0.01)
    assert [item.escalation_type.value for item in response.escalation_breakdown] == [
        "Natural",
        "Failure",
        "None",
    ]
    assert [item.count for item in response.escalation_breakdown] == [1, 1, 1]
    assert response.user_signals.avg_satisfaction_score == pytest.approx(
        6.33,
        abs=0.01,
    )
    assert response.user_signals.avg_frustration_score == pytest.approx(3.67, abs=0.01)
    assert response.user_signals.user_relevancy_rate_pct == pytest.approx(
        66.67,
        abs=0.01,
    )


@pytest.mark.asyncio
async def test_get_grading_dashboard_agent_pulse_returns_zeroed_core_aggregates_for_empty_window(
    db_session,
) -> None:
    response = await get_grading_dashboard_agent_pulse(
        db_session,
        GradingDashboardWindowQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.total_graded_customer_days == 0
    assert response.overall_composite_score == 0.0
    assert response.dimension_averages.relevancy == 0.0
    assert response.dimension_averages.accuracy == 0.0
    assert response.dimension_averages.completeness == 0.0
    assert response.dimension_averages.clarity == 0.0
    assert response.dimension_averages.tone == 0.0
    assert response.health.resolution_rate_pct == 0.0
    assert response.health.avg_repetition_score == 0.0
    assert response.health.loop_detected_rate_pct == 0.0
    assert [item.count for item in response.escalation_breakdown] == [0, 0, 0]
    assert response.user_signals.avg_satisfaction_score == 0.0
    assert response.user_signals.avg_frustration_score == 0.0
    assert response.user_signals.user_relevancy_rate_pct == 0.0


@pytest.mark.asyncio
async def test_get_grading_dashboard_agent_pulse_adds_trends_top_intents_freshness_and_attention_signals(
    db_session,
) -> None:
    seed_rows = (
        ("+971500000201", date(2026, 3, 10), "policy_inquiry", 6, 7, 3, False, True, True, True, "Failure"),
        ("+971500000202", date(2026, 3, 10), "policy_inquiry", 8, 8, 2, True, False, True, False, "None"),
        ("+971500000203", date(2026, 3, 12), "claims_submission", 5, 4, 7, False, True, False, True, "Failure"),
        ("+971500000204", date(2026, 3, 12), "complaint", 7, 6, 5, True, False, True, True, "Natural"),
        ("+971500000205", date(2026, 3, 12), "document_request", 9, 9, 1, True, False, True, False, "None"),
        ("+971500000206", date(2026, 3, 12), "payment_issue", 4, 3, 8, False, True, False, True, "Failure"),
        ("+971500000207", date(2026, 3, 12), "general_inquiry", 8, 8, 2, True, False, True, False, "None"),
        ("+971500000208", date(2026, 3, 12), "policy_cancellation", 7, 6, 4, True, False, True, False, "None"),
    )
    for (
        phone_number,
        grade_date,
        intent_code,
        ai_score,
        satisfaction_score,
        frustration_score,
        resolution,
        loop_detected,
        user_relevancy,
        escalation_occurred,
        escalation_type,
    ) in seed_rows:
        await _persist_grade(
            db_session,
            phone_number=phone_number,
            grade_date=grade_date,
            intent_code=intent_code,
            relevancy_score=ai_score,
            accuracy_score=ai_score,
            completeness_score=ai_score,
            clarity_score=ai_score,
            tone_score=ai_score,
            repetition_score=6,
            satisfaction_score=satisfaction_score,
            frustration_score=frustration_score,
            resolution=resolution,
            loop_detected=loop_detected,
            user_relevancy=user_relevancy,
            escalation_occurred=escalation_occurred,
            escalation_type=escalation_type,
        )

    successful_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 12),
        created_at=datetime(2026, 3, 13, 8, 0, 0),
        finished_at=datetime(2026, 3, 13, 8, 30, 0),
    )
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.FAILED.value,
        target_end_date=date(2026, 3, 13),
        created_at=datetime(2026, 3, 13, 9, 0, 0),
        finished_at=datetime(2026, 3, 13, 9, 30, 0),
    )

    response = await get_grading_dashboard_agent_pulse(
        db_session,
        GradingDashboardWindowQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 13),
        ),
    )

    assert [point.date for point in response.trend_points] == [
        date(2026, 3, 10),
        date(2026, 3, 11),
        date(2026, 3, 12),
        date(2026, 3, 13),
    ]
    assert response.trend_points[0].overall_composite_score == pytest.approx(7.0)
    assert response.trend_points[0].satisfaction_score == pytest.approx(7.5)
    assert response.trend_points[0].frustration_score == pytest.approx(2.5)
    assert response.trend_points[1].overall_composite_score == 0.0
    assert response.trend_points[2].overall_composite_score == pytest.approx(
        6.67,
        abs=0.01,
    )
    assert response.trend_points[2].satisfaction_score == pytest.approx(6.0)
    assert response.trend_points[2].frustration_score == pytest.approx(4.5)
    assert response.trend_points[3].overall_composite_score == 0.0

    assert [item.intent_code for item in response.top_intents] == [
        "policy_inquiry",
        "claims_submission",
        "complaint",
        "document_request",
        "general_inquiry",
        "payment_issue",
    ]
    assert response.top_intents[0].count == 2
    assert all(item.count == 1 for item in response.top_intents[1:])

    assert [item.code for item in response.attention_signals] == [
        "escalation_failure_rate_high",
        "dimension_accuracy_low",
        "dimension_clarity_low",
        "dimension_completeness_low",
        "dimension_relevancy_low",
        "dimension_tone_low",
    ]
    assert response.attention_signals[0].severity.value == "warning"
    assert response.attention_signals[0].metric_key == "escalation_failure_rate_pct"

    assert response.freshness.latest_successful_run_id == successful_run.id
    assert response.freshness.latest_successful_window_end_date == date(2026, 3, 12)
    assert response.freshness.latest_successful_run_finished_at == datetime(
        2026,
        3,
        13,
        8,
        30,
        0,
    )


@pytest.mark.asyncio
async def test_get_grading_dashboard_agent_pulse_keeps_freshness_when_window_is_empty(
    db_session,
) -> None:
    successful_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 9),
        created_at=datetime(2026, 3, 10, 8, 0, 0),
        finished_at=datetime(2026, 3, 10, 8, 15, 0),
    )

    response = await get_grading_dashboard_agent_pulse(
        db_session,
        GradingDashboardWindowQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
        ),
    )

    assert [point.overall_composite_score for point in response.trend_points] == [0.0, 0.0]
    assert response.top_intents == []
    assert response.attention_signals == []
    assert response.freshness.latest_successful_run_id == successful_run.id
    assert response.freshness.latest_successful_window_end_date == date(2026, 3, 9)
