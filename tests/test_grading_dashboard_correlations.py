from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.schemas.grading_dashboard_common import GradingDashboardWindowQuery
from app.services.grading_dashboard_correlations import (
    get_grading_dashboard_correlations,
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
    satisfaction_score: int,
    frustration_score: int,
    resolution: bool | None = None,
    loop_detected: bool | None = None,
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
        satisfaction_score=satisfaction_score,
        frustration_score=frustration_score,
        resolution=resolution,
        loop_detected=loop_detected,
        escalation_type=escalation_type,
    )
    db_session.add(grade)
    await db_session.flush()
    return grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_correlations_returns_zero_filled_heatmap_and_funnel_for_empty_window(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        phone_number="+971500000000",
        grade_date=date(2026, 3, 9),
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        satisfaction_score=6,
        frustration_score=4,
    )

    response = await get_grading_dashboard_correlations(
        db_session,
        GradingDashboardWindowQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 10),
        ),
    )

    assert response.date_window.start_date == date(2026, 3, 10)
    assert response.date_window.end_date == date(2026, 3, 10)
    assert response.total_graded_customer_days == 0
    assert len(response.heatmap_cells) == 15

    heatmap_by_key = {
        (cell.dimension_key, cell.score_bucket): cell for cell in response.heatmap_cells
    }
    for dimension_key in ("relevancy", "accuracy", "completeness", "clarity", "tone"):
        for bucket in ("1-4", "5-7", "8-10"):
            cell = heatmap_by_key[(dimension_key, bucket)]
            assert cell.conversation_count == 0
            assert cell.avg_satisfaction_score == 0.0

    assert [step.step_key for step in response.failure_funnel] == [
        "total",
        "loop_detected",
        "high_frustration",
        "unresolved",
        "failure_escalation",
    ]
    assert [step.count for step in response.failure_funnel] == [0, 0, 0, 0, 0]
    assert [bucket.bucket_label for bucket in response.frustration_histogram] == [
        "1-2",
        "3-4",
        "5-6",
        "7-8",
        "9-10",
    ]
    assert [bucket.count for bucket in response.frustration_histogram] == [0, 0, 0, 0, 0]
    assert [bucket.share_pct for bucket in response.frustration_histogram] == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    assert [card.code for card in response.story_cards] == [
        "failure_escalation_rate",
        "unresolved_rate",
        "high_frustration_rate",
        "loop_detected_rate",
    ]
    assert [card.severity.value for card in response.story_cards] == [
        "info",
        "info",
        "info",
        "info",
    ]
    assert [card.metric_value for card in response.story_cards] == [0.0, 0.0, 0.0, 0.0]
    assert all(card.explanation for card in response.story_cards)
    assert response.freshness.latest_successful_run_id is None
    assert response.freshness.latest_successful_window_end_date is None
    assert response.freshness.latest_successful_run_finished_at is None


@pytest.mark.asyncio
async def test_get_grading_dashboard_correlations_returns_heatmap_cells_for_all_dimensions_and_buckets(
    db_session,
) -> None:
    target_date = date(2026, 3, 11)
    await _persist_grade(
        db_session,
        phone_number="+971500000001",
        grade_date=target_date,
        relevancy_score=2,
        accuracy_score=4,
        completeness_score=3,
        clarity_score=1,
        tone_score=4,
        satisfaction_score=2,
        frustration_score=8,
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000002",
        grade_date=target_date,
        relevancy_score=5,
        accuracy_score=7,
        completeness_score=6,
        clarity_score=5,
        tone_score=7,
        satisfaction_score=6,
        frustration_score=5,
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000003",
        grade_date=target_date,
        relevancy_score=8,
        accuracy_score=10,
        completeness_score=9,
        clarity_score=8,
        tone_score=9,
        satisfaction_score=9,
        frustration_score=2,
    )

    response = await get_grading_dashboard_correlations(
        db_session,
        GradingDashboardWindowQuery(start_date=target_date, end_date=target_date),
    )

    assert response.total_graded_customer_days == 3
    assert len(response.heatmap_cells) == 15

    for dimension_key in ("relevancy", "accuracy", "completeness", "clarity", "tone"):
        cells = {
            cell.score_bucket: cell
            for cell in response.heatmap_cells
            if cell.dimension_key == dimension_key
        }
        assert set(cells) == {"1-4", "5-7", "8-10"}
        assert cells["1-4"].conversation_count == 1
        assert cells["1-4"].avg_satisfaction_score == 2.0
        assert cells["5-7"].conversation_count == 1
        assert cells["5-7"].avg_satisfaction_score == 6.0
        assert cells["8-10"].conversation_count == 1
        assert cells["8-10"].avg_satisfaction_score == 9.0


@pytest.mark.asyncio
async def test_get_grading_dashboard_correlations_uses_sequential_failure_funnel_counts(
    db_session,
) -> None:
    target_date = date(2026, 3, 12)
    await _persist_grade(
        db_session,
        phone_number="+971500000011",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        satisfaction_score=3,
        frustration_score=8,
        resolution=False,
        loop_detected=True,
        escalation_type="Failure",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000012",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        satisfaction_score=5,
        frustration_score=7,
        resolution=True,
        loop_detected=True,
        escalation_type="None",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000013",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        satisfaction_score=4,
        frustration_score=3,
        resolution=False,
        loop_detected=True,
        escalation_type="Failure",
    )
    await _persist_grade(
        db_session,
        phone_number="+971500000014",
        grade_date=target_date,
        relevancy_score=7,
        accuracy_score=7,
        completeness_score=7,
        clarity_score=7,
        tone_score=7,
        satisfaction_score=2,
        frustration_score=9,
        resolution=False,
        loop_detected=False,
        escalation_type="Failure",
    )

    response = await get_grading_dashboard_correlations(
        db_session,
        GradingDashboardWindowQuery(start_date=target_date, end_date=target_date),
    )

    assert [step.step_key for step in response.failure_funnel] == [
        "total",
        "loop_detected",
        "high_frustration",
        "unresolved",
        "failure_escalation",
    ]
    assert [step.count for step in response.failure_funnel] == [4, 3, 2, 1, 1]


@pytest.mark.asyncio
async def test_get_grading_dashboard_correlations_returns_fixed_frustration_histogram_buckets(
    db_session,
) -> None:
    target_date = date(2026, 3, 13)
    scores = [1, 4, 6, 7, 10]
    for index, frustration_score in enumerate(scores, start=1):
        await _persist_grade(
            db_session,
            phone_number=f"+9715000001{index:02d}",
            grade_date=target_date,
            relevancy_score=7,
            accuracy_score=7,
            completeness_score=7,
            clarity_score=7,
            tone_score=7,
            satisfaction_score=6,
            frustration_score=frustration_score,
        )

    response = await get_grading_dashboard_correlations(
        db_session,
        GradingDashboardWindowQuery(start_date=target_date, end_date=target_date),
    )

    assert [bucket.bucket_label for bucket in response.frustration_histogram] == [
        "1-2",
        "3-4",
        "5-6",
        "7-8",
        "9-10",
    ]
    assert [bucket.count for bucket in response.frustration_histogram] == [1, 1, 1, 1, 1]
    assert [bucket.share_pct for bucket in response.frustration_histogram] == [
        20.0,
        20.0,
        20.0,
        20.0,
        20.0,
    ]


@pytest.mark.asyncio
async def test_get_grading_dashboard_correlations_returns_story_cards_in_stable_severity_order(
    db_session,
) -> None:
    target_date = date(2026, 3, 14)
    for index in range(1, 21):
        await _persist_grade(
            db_session,
            phone_number=f"+9715000002{index:02d}",
            grade_date=target_date,
            relevancy_score=7,
            accuracy_score=7,
            completeness_score=7,
            clarity_score=7,
            tone_score=7,
            satisfaction_score=6,
            frustration_score=2,
            resolution=True,
            loop_detected=False,
            escalation_type="None",
        )

    seeded_rows = (await db_session.execute(
        select(ConversationGrade)
        .where(ConversationGrade.grade_date == target_date)
        .order_by(ConversationGrade.id)
    )).scalars().all()

    seeded_rows[0].loop_detected = True
    seeded_rows[1].loop_detected = True
    seeded_rows[2].loop_detected = True
    seeded_rows[0].frustration_score = 8
    seeded_rows[1].frustration_score = 8
    seeded_rows[0].resolution = False

    response = await get_grading_dashboard_correlations(
        db_session,
        GradingDashboardWindowQuery(start_date=target_date, end_date=target_date),
    )

    assert [card.code for card in response.story_cards] == [
        "high_frustration_rate",
        "loop_detected_rate",
        "unresolved_rate",
        "failure_escalation_rate",
    ]
    assert [card.severity.value for card in response.story_cards] == [
        "critical",
        "critical",
        "warning",
        "info",
    ]
    assert [card.metric_value for card in response.story_cards] == [10.0, 15.0, 5.0, 0.0]
    assert all(card.title for card in response.story_cards)
    assert all(card.metric_key for card in response.story_cards)
    assert all(card.explanation for card in response.story_cards)
