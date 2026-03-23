from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.models.chats import ChatMessage
from app.models.enums import IdentityType
from app.services.grading_extraction import (
    CustomerDayCandidate,
    assemble_customer_day_transcript,
    list_customer_day_candidates,
)


def _chat(
    *,
    created_at: datetime,
    customer_phone: str | None = None,
    customer_email_address: str | None = None,
    session_id: str | None = None,
    message: str | None = "hello",
    direction: str = "inbound",
    channel: str = "web",
    message_type: str | None = "text",
    intent: str | None = None,
    escalated: str | None = None,
) -> ChatMessage:
    return ChatMessage(
        created_at=created_at,
        customer_phone=customer_phone,
        customer_email_address=customer_email_address,
        session_id=session_id,
        message=message,
        direction=direction,
        channel=channel,
        message_type=message_type,
        intent=intent,
        escalated=escalated,
    )


async def _seed(db_session, *rows: ChatMessage) -> None:
    db_session.add_all(list(rows))
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_customer_day_candidates_prefers_canonical_identity_and_skips_unusable_rows(
    db_session,
) -> None:
    target_date = datetime(2026, 3, 5, 12, 0, 0)

    await _seed(
        db_session,
        _chat(
            created_at=target_date,
            customer_phone="  +971500000001  ",
            customer_email_address="phone-fallback@example.com",
            session_id="phone-session",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=1),
            customer_phone="+971500000001",
            message="same phone same day duplicate candidate",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=2),
            customer_phone="+971500000001",
            message="third phone message to satisfy grading threshold",
        ),
        _chat(
            created_at=target_date,
            customer_email_address="  broker@example.com  ",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=1),
            customer_email_address="broker@example.com",
            message="second email message",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=2),
            customer_email_address="broker@example.com",
            message="third email message",
        ),
        _chat(
            created_at=target_date,
            session_id="  sess-100  ",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=1),
            session_id="sess-100",
            message="second session message",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=2),
            session_id="sess-100",
            message="third session message",
        ),
        _chat(
            created_at=target_date,
            customer_phone="   ",
            customer_email_address=None,
            session_id=" ",
        ),
    )

    candidates = await list_customer_day_candidates(
        db_session,
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 5),
    )

    assert candidates == [
        CustomerDayCandidate(
            identity_type=IdentityType.EMAIL,
            conversation_identity="broker@example.com",
            grade_date=date(2026, 3, 5),
        ),
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000001",
            grade_date=date(2026, 3, 5),
        ),
        CustomerDayCandidate(
            identity_type=IdentityType.SESSION,
            conversation_identity="sess-100",
            grade_date=date(2026, 3, 5),
        ),
    ]


@pytest.mark.asyncio
async def test_list_customer_day_candidates_filters_by_grade_date(db_session) -> None:
    await _seed(
        db_session,
        _chat(
            created_at=datetime(2026, 3, 4, 11, 0, 0),
            customer_phone="+971500000002",
        ),
        _chat(
            created_at=datetime(2026, 3, 5, 11, 0, 0),
            customer_phone="+971500000002",
        ),
        _chat(
            created_at=datetime(2026, 3, 5, 11, 1, 0),
            customer_phone="+971500000002",
        ),
        _chat(
            created_at=datetime(2026, 3, 5, 11, 2, 0),
            customer_phone="+971500000002",
        ),
    )

    candidates = await list_customer_day_candidates(
        db_session,
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 5),
    )

    assert candidates == [
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000002",
            grade_date=date(2026, 3, 5),
        )
    ]


@pytest.mark.asyncio
async def test_list_customer_day_candidates_requires_three_inbound_human_messages(
    db_session,
) -> None:
    target_date = datetime(2026, 3, 7, 10, 0, 0)

    await _seed(
        db_session,
        _chat(
            created_at=target_date,
            customer_phone="+971500000010",
            direction="inbound",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=1),
            customer_phone="+971500000010",
            direction="incoming",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=2),
            customer_phone="+971500000010",
            direction="outbound",
        ),
        _chat(
            created_at=target_date,
            customer_phone="+971500000011",
            direction="inbound",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=1),
            customer_phone="+971500000011",
            direction="customer",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=2),
            customer_phone="+971500000011",
            direction="outbound",
        ),
        _chat(
            created_at=target_date + timedelta(minutes=3),
            customer_phone="+971500000011",
            direction="in",
        ),
    )

    candidates = await list_customer_day_candidates(
        db_session,
        start_date=date(2026, 3, 7),
        end_date=date(2026, 3, 7),
    )

    assert candidates == [
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000011",
            grade_date=date(2026, 3, 7),
        )
    ]


@pytest.mark.asyncio
async def test_assemble_customer_day_transcript_orders_messages_and_normalizes_content(
    db_session,
) -> None:
    base_time = datetime(2026, 3, 6, 9, 0, 0)
    phone = "+971500000003"

    await _seed(
        db_session,
        _chat(
            created_at=base_time,
            customer_phone=phone,
            message="  Hello\nthere  ",
            direction="incoming",
            channel="wa",
            message_type="message",
            intent="  Policy Inquiry  ",
            escalated="yes",
        ),
        _chat(
            created_at=base_time,
            customer_phone=phone,
            message="  https://cdn.example.com/image.png  ",
            direction="outbound",
            channel="web_chat",
            message_type="photo",
            escalated="no",
        ),
        _chat(
            created_at=base_time + timedelta(minutes=1),
            customer_phone=phone,
            message="   ",
            direction="out",
            channel="whatsapp",
            message_type=None,
            intent=" ",
            escalated="maybe",
        ),
    )

    transcript = await assemble_customer_day_transcript(
        db_session,
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity=phone,
            grade_date=date(2026, 3, 6),
        ),
    )

    assert [message.chat_id for message in transcript.messages] == sorted(
        message.chat_id for message in transcript.messages
    )

    first, second, third = transcript.messages

    assert first.direction == "inbound"
    assert first.channel == "whatsapp"
    assert first.message_type == "text"
    assert first.message == "Hello there"
    assert first.intent == "Policy Inquiry"
    assert first.escalated is True
    assert first.normalized_content == "Hello there"

    assert second.direction == "outbound"
    assert second.channel == "web"
    assert second.message_type == "image"
    assert second.escalated is False
    assert second.normalized_content == "[image attachment] https://cdn.example.com/image.png"

    assert third.direction == "outbound"
    assert third.channel == "whatsapp"
    assert third.message_type == "text"
    assert third.intent is None
    assert third.escalated is None
    assert third.normalized_content == "[empty text message]"
    assert "intent=<none>" in third.transcript_line
    assert "escalated=unknown" in third.transcript_line

    assert transcript.transcript_text.splitlines() == [
        message.transcript_line for message in transcript.messages
    ]
    assert transcript.transcript_text.startswith(
        "2026-03-06T09:00:00 | direction=inbound | channel=whatsapp"
    )
