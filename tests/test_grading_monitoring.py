from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun
from app.schemas.grading_monitoring import MonitoringConversationListQuery
from app.schemas.grading_runs import (
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)
from app.services.conversations import encode_conversation_key
from app.services.grading_monitoring import (
    get_monitoring_conversation_list,
    list_monitoring_conversation_grades,
)


async def _persist_grade(
    db_session,
    *,
    conversation_identity: str,
    grade_date: date,
    identity_type: IdentityType = IdentityType.PHONE,
    contact_phone: str | None = None,
    resolution: bool | None = None,
    escalation_type: str | None = None,
    frustration_score: int | None = None,
    accuracy_score: int | None = None,
    intent_code: str | None = "policy_inquiry",
    intent_label: str | None = "Policy Inquiry",
) -> ConversationGrade:
    grade = ConversationGrade(
        phone_number=contact_phone or conversation_identity,
        grade_date=grade_date,
        identity_type=identity_type,
        conversation_identity=conversation_identity,
        intent_code=intent_code,
        intent_label=intent_label,
        resolution=resolution,
        escalation_type=escalation_type,
        frustration_score=frustration_score,
        accuracy_score=accuracy_score,
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
    message: str,
    customer_name: str = "Test Contact",
) -> ChatMessage:
    kwargs = {
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
        direction="inbound",
        channel="whatsapp",
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
async def test_list_monitoring_conversation_grades_applies_default_order_and_pagination(
    db_session,
) -> None:
    first = await _persist_grade(
        db_session,
        conversation_identity="+971500000001",
        grade_date=date(2026, 3, 11),
        frustration_score=4,
        accuracy_score=7,
    )
    second = await _persist_grade(
        db_session,
        conversation_identity="+971500000002",
        grade_date=date(2026, 3, 11),
        frustration_score=5,
        accuracy_score=6,
    )
    third = await _persist_grade(
        db_session,
        conversation_identity="+971500000003",
        grade_date=date(2026, 3, 10),
        frustration_score=6,
        accuracy_score=5,
    )

    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=first.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 11, 0, 0),
        message="Latest message for first row",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=second.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 9, 0, 0),
        message="Latest message for second row",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=third.conversation_identity or "",
        created_at=datetime(2026, 3, 10, 23, 0, 0),
        message="Latest message for third row",
    )

    page = await list_monitoring_conversation_grades(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
            limit=2,
            offset=0,
        ),
    )

    assert page.total == 3
    assert [row.grade.id for row in page.items] == [first.id, second.id]
    assert [row.latest_message_at for row in page.items] == [
        datetime(2026, 3, 11, 11, 0, 0),
        datetime(2026, 3, 11, 9, 0, 0),
    ]

    next_page = await list_monitoring_conversation_grades(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
            limit=2,
            offset=2,
        ),
    )

    assert next_page.total == 3
    assert [row.grade.id for row in next_page.items] == [third.id]


@pytest.mark.asyncio
async def test_list_monitoring_conversation_grades_applies_filters_and_explicit_sort(
    db_session,
) -> None:
    excluded_resolution = await _persist_grade(
        db_session,
        conversation_identity="+971500000010",
        grade_date=date(2026, 3, 11),
        resolution=True,
        escalation_type="Failure",
        frustration_score=8,
        accuracy_score=2,
        intent_code="complaint",
        intent_label="Complaint",
    )
    excluded_escalation = await _persist_grade(
        db_session,
        conversation_identity="+971500000011",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Natural",
        frustration_score=8,
        accuracy_score=2,
        intent_code="complaint",
        intent_label="Complaint",
    )
    excluded_frustration = await _persist_grade(
        db_session,
        conversation_identity="+971500000012",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=6,
        accuracy_score=2,
        intent_code="complaint",
        intent_label="Complaint",
    )
    excluded_accuracy = await _persist_grade(
        db_session,
        conversation_identity="+971500000013",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=8,
        accuracy_score=4,
        intent_code="complaint",
        intent_label="Complaint",
    )
    excluded_intent = await _persist_grade(
        db_session,
        conversation_identity="+971500000014",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=8,
        accuracy_score=2,
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
    )
    higher_accuracy = await _persist_grade(
        db_session,
        conversation_identity="+971500000015",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=9,
        accuracy_score=3,
        intent_code="complaint",
        intent_label="Complaint",
    )
    lower_accuracy = await _persist_grade(
        db_session,
        conversation_identity="+971500000016",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=7,
        accuracy_score=1,
        intent_code="complaint",
        intent_label="Complaint",
    )

    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=lower_accuracy.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 8, 0, 0),
        message="Matching chat one",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=higher_accuracy.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 9, 0, 0),
        message="Matching chat two",
    )

    page = await list_monitoring_conversation_grades(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 11),
            end_date=date(2026, 3, 11),
            resolution=False,
            escalation_types=["Failure"],
            frustration_min=7,
            accuracy_max=3,
            intent_codes=["complaint"],
            sort_by="accuracy_score",
            sort_direction="asc",
        ),
    )

    assert page.total == 2
    assert [row.grade.id for row in page.items] == [
        lower_accuracy.id,
        higher_accuracy.id,
    ]
    assert excluded_resolution.id not in [row.grade.id for row in page.items]
    assert excluded_escalation.id not in [row.grade.id for row in page.items]
    assert excluded_frustration.id not in [row.grade.id for row in page.items]
    assert excluded_accuracy.id not in [row.grade.id for row in page.items]
    assert excluded_intent.id not in [row.grade.id for row in page.items]


@pytest.mark.asyncio
async def test_list_monitoring_conversation_grades_returns_empty_page_for_empty_window(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        conversation_identity="+971500000020",
        grade_date=date(2026, 3, 8),
        frustration_score=3,
        accuracy_score=8,
    )

    page = await list_monitoring_conversation_grades(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 9),
            end_date=date(2026, 3, 9),
        ),
    )

    assert page.total == 0
    assert page.items == []


@pytest.mark.asyncio
async def test_get_monitoring_conversation_list_excludes_legacy_phone_only_grade_rows(
    db_session,
) -> None:
    await _persist_grade(
        db_session,
        conversation_identity="+971500000021",
        contact_phone="+971500000021",
        grade_date=date(2026, 3, 11),
    )
    legacy_grade = ConversationGrade(
        phone_number="+971500000099",
        grade_date=date(2026, 3, 11),
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        frustration_score=5,
        accuracy_score=7,
    )
    db_session.add(legacy_grade)
    await db_session.flush()

    response = await get_monitoring_conversation_list(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 11),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].grade_id != legacy_grade.id


@pytest.mark.asyncio
async def test_get_monitoring_conversation_list_enriches_items_with_preview_highlights_and_freshness(
    db_session,
) -> None:
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500000030",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=8,
        accuracy_score=3,
        intent_code="complaint",
        intent_label="Complaint",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 10, 0, 0),
        message="Earlier message",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 11, 30, 0),
        message="Latest message for analysts",
    )
    successful_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED_WITH_FAILURES.value,
        target_end_date=date(2026, 3, 11),
        created_at=datetime(2026, 3, 12, 9, 0, 0),
        finished_at=datetime(2026, 3, 12, 9, 30, 0),
    )

    response = await get_monitoring_conversation_list(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 11),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.total == 1
    assert response.items[0].grade_id == grade.id
    assert response.items[0].conversation_key == encode_conversation_key(
        grade.conversation_identity or ""
    )
    assert response.items[0].latest_message_preview == "Latest message for analysts"
    assert response.items[0].latest_message_at == datetime(2026, 3, 11, 11, 30, 0)
    assert response.items[0].message_count == 2
    assert response.items[0].intent_code == "complaint"
    assert response.items[0].intent_label == "Complaint"
    assert response.items[0].intent_category == "Support & Complaints"
    assert [badge.code for badge in response.items[0].highlights] == [
        "frustration_high",
        "escalation_failure",
        "accuracy_low",
    ]
    assert response.freshness.latest_successful_run_id == successful_run.id
    assert response.freshness.latest_successful_window_end_date == date(2026, 3, 11)
    assert response.freshness.latest_successful_run_finished_at == datetime(
        2026, 3, 12, 9, 30, 0
    )


@pytest.mark.asyncio
async def test_get_monitoring_conversation_list_keeps_freshness_when_window_is_empty(
    db_session,
) -> None:
    successful_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_end_date=date(2026, 3, 10),
        created_at=datetime(2026, 3, 12, 8, 0, 0),
        finished_at=datetime(2026, 3, 12, 8, 15, 0),
    )

    response = await get_monitoring_conversation_list(
        db_session,
        MonitoringConversationListQuery(
            start_date=date(2026, 3, 11),
            end_date=date(2026, 3, 11),
        ),
    )

    assert response.total == 0
    assert response.items == []
    assert response.freshness.latest_successful_run_id == successful_run.id
    assert response.freshness.latest_successful_window_end_date == date(2026, 3, 10)
    assert response.freshness.latest_successful_run_finished_at == datetime(
        2026, 3, 12, 8, 15, 0
    )
