from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.services.conversations import encode_conversation_key
from app.services.grading_monitoring import (
    MonitoringConversationNotFoundError,
    get_monitoring_conversation_detail,
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
    relevancy_score: int | None = None,
    relevancy_reasoning: str | None = None,
    accuracy_reasoning: str | None = None,
    completeness_score: int | None = None,
    completeness_reasoning: str | None = None,
    clarity_score: int | None = None,
    clarity_reasoning: str | None = None,
    tone_score: int | None = None,
    tone_reasoning: str | None = None,
    resolution_reasoning: str | None = None,
    repetition_score: int | None = None,
    repetition_reasoning: str | None = None,
    loop_detected: bool | None = None,
    loop_detected_reasoning: str | None = None,
    satisfaction_score: int | None = None,
    satisfaction_reasoning: str | None = None,
    frustration_reasoning: str | None = None,
    user_relevancy: bool | None = None,
    user_relevancy_reasoning: str | None = None,
    escalation_occurred: bool | None = None,
    escalation_occurred_reasoning: str | None = None,
    escalation_type_reasoning: str | None = None,
    intent_reasoning: str | None = None,
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
        intent_reasoning=intent_reasoning,
        relevancy_score=relevancy_score,
        relevancy_reasoning=relevancy_reasoning,
        resolution=resolution,
        resolution_reasoning=resolution_reasoning,
        escalation_type=escalation_type,
        escalation_type_reasoning=escalation_type_reasoning,
        escalation_occurred=escalation_occurred,
        escalation_occurred_reasoning=escalation_occurred_reasoning,
        frustration_score=frustration_score,
        frustration_reasoning=frustration_reasoning,
        accuracy_score=accuracy_score,
        accuracy_reasoning=accuracy_reasoning,
        completeness_score=completeness_score,
        completeness_reasoning=completeness_reasoning,
        clarity_score=clarity_score,
        clarity_reasoning=clarity_reasoning,
        tone_score=tone_score,
        tone_reasoning=tone_reasoning,
        repetition_score=repetition_score,
        repetition_reasoning=repetition_reasoning,
        loop_detected=loop_detected,
        loop_detected_reasoning=loop_detected_reasoning,
        satisfaction_score=satisfaction_score,
        satisfaction_reasoning=satisfaction_reasoning,
        user_relevancy=user_relevancy,
        user_relevancy_reasoning=user_relevancy_reasoning,
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
    direction: str = "inbound",
    channel: str = "whatsapp",
    message_type: str = "text",
    intent: str | None = None,
    escalated: str | None = None,
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
        direction=direction,
        channel=channel,
        message_type=message_type,
        intent=intent,
        escalated=escalated,
        created_at=created_at,
    )
    db_session.add(chat)
    await db_session.flush()
    return chat


@pytest.mark.asyncio
async def test_get_monitoring_conversation_detail_returns_grouped_panel_and_transcript(
    db_session,
) -> None:
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500000030",
        grade_date=date(2026, 3, 11),
        identity_type=IdentityType.PHONE,
        intent_code="complaint",
        intent_label="Complaint",
        intent_reasoning="The customer complained about a delayed claim response.",
        relevancy_score=6,
        relevancy_reasoning="The assistant partly addressed the claim question.",
        accuracy_score=3,
        accuracy_reasoning="The policy waiting period was stated incorrectly.",
        completeness_score=5,
        completeness_reasoning="The answer missed the escalation route.",
        clarity_score=7,
        clarity_reasoning="The message was understandable.",
        tone_score=6,
        tone_reasoning="The tone remained polite but slightly repetitive.",
        resolution=False,
        resolution_reasoning="The customer still needed a human follow-up.",
        repetition_score=8,
        repetition_reasoning="The assistant repeated the same next step twice.",
        loop_detected=True,
        loop_detected_reasoning="The conversation cycled without new progress.",
        satisfaction_score=2,
        satisfaction_reasoning="The customer explicitly remained unhappy.",
        frustration_score=8,
        frustration_reasoning="The customer expressed visible frustration.",
        user_relevancy=True,
        user_relevancy_reasoning="The conversation was a genuine insurance support request.",
        escalation_occurred=True,
        escalation_occurred_reasoning="The chat was escalated to a human agent.",
        escalation_type="Failure",
        escalation_type_reasoning="The escalation happened because the bot failed to resolve the issue.",
    )

    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 9, 15, 0),
        message="I still need help with my claim.",
        customer_name="Jane Customer",
        direction="inbound",
        intent="Complaint",
        escalated="true",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 9, 17, 0),
        message="We are connecting you to a specialist.",
        customer_name="Jane Customer",
        direction="outbound",
        intent="Complaint",
        escalated="true",
    )

    detail = await get_monitoring_conversation_detail(db_session, grade.id)

    assert detail.grade_id == grade.id
    assert detail.contact_name == "Jane Customer"
    assert detail.latest_message_preview == "We are connecting you to a specialist."
    assert detail.latest_message_at == datetime(2026, 3, 11, 9, 17, 0)
    assert detail.message_count == 2
    assert detail.intent_code == "complaint"
    assert detail.intent_label == "Complaint"
    assert detail.intent_category == "Support & Complaints"
    assert [badge.code for badge in detail.highlights] == [
        "frustration_high",
        "escalation_failure",
        "loop_detected",
        "accuracy_low",
        "unresolved_low_satisfaction",
    ]
    assert [message.role for message in detail.transcript] == ["user", "assistant"]
    assert [message.content for message in detail.transcript] == [
        "I still need help with my claim.",
        "We are connecting you to a specialist.",
    ]
    assert detail.grade_panel.ai_performance == {
        "relevancy_score": 6,
        "relevancy_reasoning": "The assistant partly addressed the claim question.",
        "accuracy_score": 3,
        "accuracy_reasoning": "The policy waiting period was stated incorrectly.",
        "completeness_score": 5,
        "completeness_reasoning": "The answer missed the escalation route.",
        "clarity_score": 7,
        "clarity_reasoning": "The message was understandable.",
        "tone_score": 6,
        "tone_reasoning": "The tone remained polite but slightly repetitive.",
    }
    assert detail.grade_panel.conversation_health == {
        "resolution": False,
        "resolution_reasoning": "The customer still needed a human follow-up.",
        "repetition_score": 8,
        "repetition_reasoning": "The assistant repeated the same next step twice.",
        "loop_detected": True,
        "loop_detected_reasoning": "The conversation cycled without new progress.",
    }
    assert detail.grade_panel.user_signals == {
        "satisfaction_score": 2,
        "satisfaction_reasoning": "The customer explicitly remained unhappy.",
        "frustration_score": 8,
        "frustration_reasoning": "The customer expressed visible frustration.",
        "user_relevancy": True,
        "user_relevancy_reasoning": "The conversation was a genuine insurance support request.",
    }
    assert detail.grade_panel.escalation == {
        "escalation_occurred": True,
        "escalation_occurred_reasoning": "The chat was escalated to a human agent.",
        "escalation_type": "Failure",
        "escalation_type_reasoning": "The escalation happened because the bot failed to resolve the issue.",
    }
    assert detail.grade_panel.intent == {
        "intent_code": "complaint",
        "intent_label": "Complaint",
        "intent_category": "Support & Complaints",
        "intent_reasoning": "The customer complained about a delayed claim response.",
    }
    assert detail.recent_history == []


@pytest.mark.asyncio
async def test_get_monitoring_conversation_detail_raises_for_unknown_grade(
    db_session,
) -> None:
    with pytest.raises(MonitoringConversationNotFoundError, match="Grade not found"):
        await get_monitoring_conversation_detail(db_session, uuid4())


@pytest.mark.asyncio
async def test_get_monitoring_conversation_detail_raises_when_same_day_messages_are_missing(
    db_session,
) -> None:
    grade = await _persist_grade(
        db_session,
        conversation_identity="+971500000031",
        grade_date=date(2026, 3, 11),
        identity_type=IdentityType.PHONE,
    )

    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 10, 23, 0, 0),
        message="Previous day only",
    )

    with pytest.raises(MonitoringConversationNotFoundError, match="Grade not found"):
        await get_monitoring_conversation_detail(db_session, grade.id)


@pytest.mark.asyncio
async def test_get_monitoring_conversation_detail_adds_recent_history_and_linkage(
    db_session,
) -> None:
    conversation_identity = "+971500000040"
    current = await _persist_grade(
        db_session,
        conversation_identity=conversation_identity,
        grade_date=date(2026, 3, 11),
        identity_type=IdentityType.PHONE,
        resolution=True,
        escalation_type="None",
        frustration_score=2,
        accuracy_score=8,
    )
    history_one = await _persist_grade(
        db_session,
        conversation_identity=conversation_identity,
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=False,
        escalation_type="Failure",
        frustration_score=8,
        accuracy_score=2,
        loop_detected=True,
        satisfaction_score=2,
    )
    history_two = await _persist_grade(
        db_session,
        conversation_identity=conversation_identity,
        grade_date=date(2026, 3, 9),
        identity_type=IdentityType.PHONE,
        resolution=False,
        escalation_type="Natural",
        frustration_score=7,
        accuracy_score=6,
        user_relevancy=False,
    )
    await _persist_grade(
        db_session,
        conversation_identity="+971500000041",
        grade_date=date(2026, 3, 10),
        identity_type=IdentityType.PHONE,
        resolution=False,
        escalation_type="Failure",
        frustration_score=9,
        accuracy_score=1,
    )

    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=conversation_identity,
        created_at=datetime(2026, 3, 11, 10, 0, 0),
        message="Current day transcript message",
    )

    detail = await get_monitoring_conversation_detail(
        db_session,
        current.id,
        history_limit=2,
    )

    assert detail.conversation_key == encode_conversation_key(conversation_identity)
    assert [item.grade_id for item in detail.recent_history] == [
        history_one.id,
        history_two.id,
    ]
    assert [item.grade_date for item in detail.recent_history] == [
        date(2026, 3, 10),
        date(2026, 3, 9),
    ]
    assert [item.conversation_key for item in detail.recent_history] == [
        encode_conversation_key(conversation_identity),
        encode_conversation_key(conversation_identity),
    ]
    assert [item.resolution for item in detail.recent_history] == [False, False]
    assert [item.escalation_type for item in detail.recent_history] == [
        "Failure",
        "Natural",
    ]
    assert [item.frustration_score for item in detail.recent_history] == [8, 7]
    assert [item.accuracy_score for item in detail.recent_history] == [2, 6]
    assert [badge.code for badge in detail.recent_history[0].highlights] == [
        "frustration_high",
        "escalation_failure",
        "loop_detected",
        "accuracy_low",
        "unresolved_low_satisfaction",
    ]
    assert [badge.code for badge in detail.recent_history[1].highlights] == [
        "frustration_high",
        "user_irrelevancy",
    ]
