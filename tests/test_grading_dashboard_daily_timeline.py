from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun
from app.schemas.grading_dashboard_common import GradingDashboardDailyTimelineQuery
from app.schemas.grading_runs import (
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)
from app.services.conversations import encode_conversation_key
from app.services.grading_dashboard_daily_timeline import (
    get_grading_dashboard_daily_timeline,
)


async def _persist_grade(
    db_session,
    *,
    conversation_identity: str,
    grade_date: date,
    identity_type: IdentityType = IdentityType.PHONE,
    resolution: bool | None = None,
    loop_detected: bool | None = None,
    satisfaction_score: int | None = None,
    frustration_score: int | None = None,
    relevancy_score: int | None = None,
    accuracy_score: int | None = None,
    completeness_score: int | None = None,
    clarity_score: int | None = None,
    tone_score: int | None = None,
    escalation_type: str | None = None,
    intent_code: str | None = None,
    intent_label: str | None = None,
) -> ConversationGrade:
    grade = ConversationGrade(
        phone_number=conversation_identity,
        grade_date=grade_date,
        identity_type=identity_type,
        conversation_identity=conversation_identity,
        resolution=resolution,
        loop_detected=loop_detected,
        satisfaction_score=satisfaction_score,
        frustration_score=frustration_score,
        relevancy_score=relevancy_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        clarity_score=clarity_score,
        tone_score=tone_score,
        escalation_type=escalation_type,
        intent_code=intent_code,
        intent_label=intent_label,
    )
    db_session.add(grade)
    await db_session.flush()
    return grade


async def _persist_chat(
    db_session,
    *,
    identity_type: IdentityType,
    conversation_identity: str,
    created_at: datetime,
    message: str = "Test message",
    customer_name: str | None = None,
    direction: str = "inbound",
    channel: str = "whatsapp",
) -> ChatMessage:
    kwargs: dict = {
        "customer_phone": None,
        "customer_email_address": None,
        "session_id": None,
    }
    if identity_type is IdentityType.PHONE:
        kwargs["customer_phone"] = conversation_identity
    elif identity_type is IdentityType.EMAIL:
        kwargs["customer_email_address"] = conversation_identity
    else:
        kwargs["session_id"] = conversation_identity

    chat = ChatMessage(
        **kwargs,
        customer_name=customer_name,
        message=message,
        direction=direction,
        channel=channel,
        message_type="text",
        created_at=created_at,
    )
    db_session.add(chat)
    await db_session.flush()
    return chat


async def _persist_run(
    db_session,
    *,
    status: str,
    target_end_date: date,
    finished_at: datetime | None = None,
) -> GradingRun:
    created_at = datetime(2026, 3, 14, 8, 0, 0)
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
async def test_get_grading_dashboard_daily_timeline_zero_filled_for_empty_day(
    db_session,
) -> None:
    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.target_date == date(2026, 3, 10)
    assert len(result.hourly_buckets) == 24
    assert [b.hour for b in result.hourly_buckets] == list(range(24))
    assert all(b.conversation_volume == 0 for b in result.hourly_buckets)
    assert all(b.resolution_rate_pct == 0.0 for b in result.hourly_buckets)
    assert result.best_hour is None
    assert result.worst_hour is None
    assert result.scatter_points == []
    assert result.worst_performers == []


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_hourly_buckets_use_raw_chat_timestamps(
    db_session,
) -> None:
    # The Daily Timeline service must bucket by the same reporting-hour
    # semantics as the shared same-day chat filter, not by grade-row timestamps.
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001001",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001001",
        created_at=datetime(2026, 3, 10, 5, 0, 0),
        message="First message in reporting hour 1",
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[1].conversation_volume == 1
    assert result.hourly_buckets[1].resolution_rate_pct == 100.0
    for h in range(24):
        if h != 1:
            assert result.hourly_buckets[h].conversation_volume == 0

    assert result.best_hour is not None
    assert result.best_hour.hour == 1
    assert result.best_hour.conversation_volume == 1
    assert result.best_hour.resolution_rate_pct == 100.0

    assert result.worst_hour is not None
    assert result.worst_hour.hour == 1

    del grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_hourly_bucket_uses_shared_reporting_hour_not_raw_utc_hour(
    db_session,
) -> None:
    # The service must use the shared SQL reporting-hour derivation rather than
    # the raw stored timestamp hour.
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001098",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001098",
        created_at=datetime(2026, 3, 10, 5, 0, 0),
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[1].conversation_volume == 1
    assert result.hourly_buckets[5].conversation_volume == 0   # raw UTC hour — must not be used
    del grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_hour_bucket_matches_shared_date_filter_semantics(
    db_session,
) -> None:
    # Boundary regression: the same-day date filter and hour bucket must use the
    # same SQL reporting-time derivation for edge-case timestamps.
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001099",
        grade_date=date(2026, 3, 9),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001099",
        created_at=datetime(2026, 3, 9, 21, 30, 0),
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 9))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[17].conversation_volume == 1
    assert result.hourly_buckets[1].conversation_volume == 0
    del grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_hourly_bucketing_ignores_grade_created_at(
    db_session,
) -> None:
    # The chat timestamp must drive the bucket even when grade-row timestamps
    # point elsewhere.
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001002",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=False,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001002",
        created_at=datetime(2026, 3, 10, 11, 0, 0),
        message="Message in reporting hour 7",
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[7].conversation_volume == 1
    assert result.hourly_buckets[11].conversation_volume == 0
    assert result.hourly_buckets[0].conversation_volume == 0
    del grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_grades_without_chat_excluded_from_hourly(
    db_session,
) -> None:
    # Grade with no matching chat messages - should not appear in hourly buckets
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001003",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
        satisfaction_score=8,
        frustration_score=2,
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert all(b.conversation_volume == 0 for b in result.hourly_buckets)
    assert result.best_hour is None
    # Scatter points still include the grade (no chat message requirement for scatter)
    assert len(result.scatter_points) == 1
    assert result.scatter_points[0].grade_id == grade.id


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_hourly_bucket_uses_first_message_hour(
    db_session,
) -> None:
    # Two messages for the same conversation on the same day, at different
    # reporting hours. The first same-day message determines the bucket.
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001004",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001004",
        created_at=datetime(2026, 3, 10, 4, 0, 0),
        message="First message",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001004",
        created_at=datetime(2026, 3, 10, 6, 0, 0),
        message="Second message",
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[0].conversation_volume == 1
    assert result.hourly_buckets[2].conversation_volume == 0
    assert result.hourly_buckets[4].conversation_volume == 0
    del grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_multiple_conversations_in_different_hours(
    db_session,
) -> None:
    grade_9am = await _persist_grade(
        db_session,
        conversation_identity="+971500001010",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001010",
        created_at=datetime(2026, 3, 10, 5, 0, 0),
    )

    grade_14pm = await _persist_grade(
        db_session,
        conversation_identity="+971500001011",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=False,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001011",
        created_at=datetime(2026, 3, 10, 10, 0, 0),
    )

    grade_9am_resolved = await _persist_grade(
        db_session,
        conversation_identity="+971500001012",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001012",
        created_at=datetime(2026, 3, 10, 5, 30, 0),
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[1].conversation_volume == 2
    assert result.hourly_buckets[1].resolution_rate_pct == 100.0
    assert result.hourly_buckets[6].conversation_volume == 1
    assert result.hourly_buckets[6].resolution_rate_pct == 0.0

    assert result.best_hour is not None
    assert result.best_hour.hour == 1
    assert result.worst_hour is not None
    assert result.worst_hour.hour == 6

    del grade_9am, grade_14pm, grade_9am_resolved


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_resolution_rate_calculated_per_hour(
    db_session,
) -> None:
    # 1 resolved, 1 unresolved in same hour
    for identity, resolution in [
        ("+971500001020", True),
        ("+971500001021", False),
    ]:
        grade = await _persist_grade(
            db_session,
            conversation_identity=identity,
            grade_date=date(2026, 3, 10),
            identity_type=IdentityType.PHONE,
            resolution=resolution,
        )
        await _persist_chat(
            db_session,
            identity_type=IdentityType.PHONE,
            conversation_identity=identity,
            created_at=datetime(2026, 3, 10, 7, 0, 0),
        )
        del grade

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.hourly_buckets[3].conversation_volume == 2
    assert result.hourly_buckets[3].resolution_rate_pct == 50.0


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_scatter_points_include_all_scored_grades(
    db_session,
) -> None:
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001030",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        satisfaction_score=7,
        frustration_score=3,
        resolution=True,
        loop_detected=False,
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.scatter_points) == 1
    point = result.scatter_points[0]
    assert point.grade_id == grade.id
    assert point.conversation_key == encode_conversation_key("+971500001030")
    assert point.satisfaction_score == 7.0
    assert point.frustration_score == 3.0
    assert point.resolution is True
    assert point.loop_detected is False


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_scatter_points_skip_incomplete_scores(
    db_session,
) -> None:
    grade_complete = await _persist_grade(
        db_session,
        conversation_identity="+971500001040",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        satisfaction_score=8,
        frustration_score=2,
    )
    # Missing satisfaction score - skip
    await _persist_grade(
        db_session,
        conversation_identity="+971500001041",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        frustration_score=5,
        satisfaction_score=None,
    )
    # Missing frustration score - skip
    await _persist_grade(
        db_session,
        conversation_identity="+971500001042",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        satisfaction_score=6,
        frustration_score=None,
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.scatter_points) == 1
    assert result.scatter_points[0].grade_id == grade_complete.id


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_worst_performers_ordered_by_composite_asc(
    db_session,
) -> None:
    # grade_low has composite sum 10 (2*5)
    grade_low = await _persist_grade(
        db_session,
        conversation_identity="+971500001050",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        relevancy_score=2,
        accuracy_score=2,
        completeness_score=2,
        clarity_score=2,
        tone_score=2,
        satisfaction_score=2,
        frustration_score=9,
        resolution=False,
    )
    # grade_high has composite sum 40 (8*5)
    grade_high = await _persist_grade(
        db_session,
        conversation_identity="+971500001051",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        relevancy_score=8,
        accuracy_score=8,
        completeness_score=8,
        clarity_score=8,
        tone_score=8,
        satisfaction_score=8,
        frustration_score=2,
        resolution=True,
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.worst_performers) == 2
    assert result.worst_performers[0].grade_id == grade_low.id
    assert result.worst_performers[1].grade_id == grade_high.id
    assert result.worst_performers[0].relevancy_score == 2
    assert result.worst_performers[0].resolution is False
    assert result.worst_performers[1].relevancy_score == 8
    assert result.worst_performers[1].resolution is True


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_worst_performers_limit_enforced(
    db_session,
) -> None:
    for i in range(5):
        await _persist_grade(
            db_session,
            conversation_identity=f"+9715000020{i:02d}",
            grade_date=date(2026, 3, 10),
            identity_type=IdentityType.PHONE,
            relevancy_score=3 + i,
            accuracy_score=3 + i,
            completeness_score=3 + i,
            clarity_score=3 + i,
            tone_score=3 + i,
            satisfaction_score=4 + i,
            frustration_score=5 - i,
        )

    query = GradingDashboardDailyTimelineQuery(
        target_date=date(2026, 3, 10),
        worst_performers_limit=3,
    )
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.worst_performers) == 3


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_worst_performers_skip_missing_ai_scores(
    db_session,
) -> None:
    grade_complete = await _persist_grade(
        db_session,
        conversation_identity="+971500001060",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        relevancy_score=4,
        accuracy_score=4,
        completeness_score=4,
        clarity_score=4,
        tone_score=4,
        satisfaction_score=4,
        frustration_score=4,
    )
    # Missing accuracy_score - excluded from worst performers
    await _persist_grade(
        db_session,
        conversation_identity="+971500001061",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        relevancy_score=4,
        accuracy_score=None,
        completeness_score=4,
        clarity_score=4,
        tone_score=4,
        satisfaction_score=4,
        frustration_score=4,
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.worst_performers) == 1
    assert result.worst_performers[0].grade_id == grade_complete.id


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_worst_performers_include_intent_metadata(
    db_session,
) -> None:
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001070",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        relevancy_score=5,
        accuracy_score=5,
        completeness_score=5,
        clarity_score=5,
        tone_score=5,
        satisfaction_score=5,
        frustration_score=5,
        escalation_type="Failure",
        intent_code="complaint",
        intent_label="Complaint",
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.worst_performers) == 1
    row = result.worst_performers[0]
    assert row.grade_id == grade.id
    assert row.escalation_type == "Failure"
    assert row.intent_code == "complaint"
    assert row.intent_label == "Complaint"
    assert row.intent_category == "Support & Complaints"


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_worst_performers_contact_label_from_chat(
    db_session,
) -> None:
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001080",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        relevancy_score=4,
        accuracy_score=4,
        completeness_score=4,
        clarity_score=4,
        tone_score=4,
        satisfaction_score=4,
        frustration_score=4,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001080",
        created_at=datetime(2026, 3, 10, 7, 0, 0),
        customer_name="John Doe",
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result.worst_performers) == 1
    assert result.worst_performers[0].contact_label == "John Doe"
    del grade


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_freshness_independent_from_grade_availability(
    db_session,
) -> None:
    # No grade rows for target_date, but a successful run exists
    run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 9),
        finished_at=datetime(2026, 3, 10, 8, 0, 0),
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 8))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.freshness.latest_successful_run_id == run.id
    assert result.freshness.latest_successful_window_end_date == date(2026, 3, 9)
    assert result.freshness.latest_successful_run_finished_at == datetime(2026, 3, 10, 8, 0, 0)
    assert result.scatter_points == []
    assert result.worst_performers == []
    assert len(result.hourly_buckets) == 24
    assert all(b.conversation_volume == 0 for b in result.hourly_buckets)


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_freshness_ignores_failed_run(
    db_session,
) -> None:
    successful_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 9),
        finished_at=datetime(2026, 3, 10, 8, 0, 0),
    )
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.FAILED.value,
        target_end_date=date(2026, 3, 10),
        finished_at=datetime(2026, 3, 11, 8, 0, 0),
    )

    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 8))
    result = await get_grading_dashboard_daily_timeline(db_session, query)

    assert result.freshness.latest_successful_run_id == successful_run.id


@pytest.mark.asyncio
async def test_get_grading_dashboard_daily_timeline_hourly_buckets_always_24_elements(
    db_session,
) -> None:
    # With or without data, there should always be exactly 24 buckets
    query = GradingDashboardDailyTimelineQuery(target_date=date(2026, 3, 10))
    result_empty = await get_grading_dashboard_daily_timeline(db_session, query)

    assert len(result_empty.hourly_buckets) == 24
    assert [b.hour for b in result_empty.hourly_buckets] == list(range(24))

    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500001090",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=True,
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500001090",
        created_at=datetime(2026, 3, 10, 8, 0, 0),  # 08:00 UTC = 12:00 GST
    )

    result_populated = await get_grading_dashboard_daily_timeline(db_session, query)
    assert len(result_populated.hourly_buckets) == 24
    assert [b.hour for b in result_populated.hourly_buckets] == list(range(24))
    del grade
