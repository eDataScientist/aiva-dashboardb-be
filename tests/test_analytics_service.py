from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models.chats import ChatMessage
from app.services import analytics as analytics_service


def _chat(
    *,
    created_at: datetime,
    session_id: str,
    direction: str = "inbound",
    channel: str = "web",
    intent: str | None = None,
    escalated: str | None = None,
    customer_phone: str | None = None,
    customer_email_address: str | None = None,
) -> ChatMessage:
    return ChatMessage(
        created_at=created_at,
        session_id=session_id,
        direction=direction,
        channel=channel,
        intent=intent,
        escalated=escalated,
        customer_phone=customer_phone,
        customer_email_address=customer_email_address,
        message="test",
    )


async def _seed(db_session, *rows: ChatMessage) -> None:
    db_session.add_all(list(rows))
    await db_session.commit()


@pytest.mark.asyncio
async def test_summary_happy_path_computes_kpis(db_session):
    await _seed(
        db_session,
        _chat(
            created_at=datetime(2026, 1, 10, 16, 0, 0),
            session_id="cust-a",
            direction="inbound",
            channel="web",
            escalated="false",
        ),
        _chat(
            created_at=datetime(2026, 1, 10, 17, 0, 0),
            session_id="cust-a",
            direction="outbound",
            channel="web",
            escalated="false",
        ),
        _chat(
            created_at=datetime(2026, 1, 10, 18, 0, 0),
            session_id="cust-b",
            direction="inbound",
            channel="whatsapp",
            escalated="true",
            intent="New Contact Form Submitted",
        ),
        _chat(
            created_at=datetime(2026, 1, 10, 19, 0, 0),
            session_id="cust-c",
            direction="inbound",
            channel="web",
            escalated="no",
        ),
    )

    result = await analytics_service.get_analytics_summary(
        session=db_session,
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
        channel="all",
    )

    assert result.total_messages == 4
    assert result.total_customers == 3
    assert result.inbound_messages == 3
    assert result.outbound_messages == 1
    assert result.escalated_customers == 1
    assert result.escalation_rate_pct == 33.33
    assert result.resolution_rate_pct == 66.67
    assert result.avg_engagement == 1.33
    assert result.total_leads == 1
    assert result.lead_conversion_rate_pct == 33.33
    assert result.ai_quality_score == 100.0


@pytest.mark.asyncio
async def test_message_volume_top_intents_and_peak_hours_happy_path(db_session):
    await _seed(
        db_session,
        _chat(
            created_at=datetime(2026, 1, 11, 14, 0, 0),
            session_id="s1",
            channel="web",
            intent="Quote",
        ),
        _chat(
            created_at=datetime(2026, 1, 11, 15, 0, 0),
            session_id="s2",
            channel="web",
            intent="Quote",
        ),
        _chat(
            created_at=datetime(2026, 1, 12, 16, 0, 0),
            session_id="s3",
            channel="web",
            intent=" ",
        ),
        _chat(
            created_at=datetime(2026, 1, 12, 17, 0, 0),
            session_id="s4",
            channel="whatsapp",
            intent=None,
        ),
    )

    volume = await analytics_service.get_message_volume_trend(
        session=db_session,
        start_date=date(2026, 1, 11),
        end_date=date(2026, 1, 13),
        channel="all",
    )
    assert [(p.date.isoformat(), p.count) for p in volume.points] == [
        ("2026-01-11", 2),
        ("2026-01-12", 2),
        ("2026-01-13", 0),
    ]

    intents = await analytics_service.get_top_intents(
        session=db_session,
        start_date=date(2026, 1, 11),
        end_date=date(2026, 1, 12),
        channel="all",
        limit=5,
    )
    assert [p.intent for p in intents.points] == ["Quote", "Unknown"]
    assert [p.count for p in intents.points] == [2, 2]
    assert [p.share_pct for p in intents.points] == [50.0, 50.0]

    peak_hours = await analytics_service.get_peak_hours(
        session=db_session,
        start_date=date(2026, 1, 11),
        end_date=date(2026, 1, 12),
        channel="all",
    )
    assert len(peak_hours.points) == 24
    assert sum(p.count for p in peak_hours.points) == 4
    assert all(point.hour == idx for idx, point in enumerate(peak_hours.points))


@pytest.mark.asyncio
async def test_quality_and_lead_conversion_trends_happy_path(db_session):
    await _seed(
        db_session,
        _chat(
            created_at=datetime(2026, 1, 14, 12, 0, 0),
            session_id="qa1",
            channel="web",
            escalated="false",
        ),
        _chat(
            created_at=datetime(2026, 1, 14, 13, 0, 0),
            session_id="qa2",
            channel="web",
            escalated="true",
            intent="New Contact Form Submitted",
        ),
        _chat(
            created_at=datetime(2026, 1, 15, 12, 0, 0),
            session_id="qa3",
            channel="web",
            escalated="no",
            intent="New Get-A-Quote Form Submitted in UAE",
        ),
    )

    quality = await analytics_service.compute_quality_trend(
        session=db_session,
        start_date=date(2026, 1, 14),
        end_date=date(2026, 1, 15),
    )
    assert [(p.date.isoformat(), p.value) for p in quality.points] == [
        ("2026-01-14", 100.0),
        ("2026-01-15", 100.0),
    ]

    lead = await analytics_service.compute_lead_conversion_trend(
        session=db_session,
        start_date=date(2026, 1, 14),
        end_date=date(2026, 1, 15),
    )
    assert [(p.date.isoformat(), p.count, p.rate_pct) for p in lead.points] == [
        ("2026-01-14", 1, 50.0),
        ("2026-01-15", 1, 100.0),
    ]


@pytest.mark.asyncio
async def test_analytics_services_empty_db_returns_zero_safe_shapes(db_session):
    summary = await analytics_service.get_analytics_summary(
        session=db_session,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 20),
        channel="all",
    )
    assert summary.total_messages == 0
    assert summary.total_customers == 0
    assert summary.ai_quality_score == 0.0

    volume = await analytics_service.get_message_volume_trend(
        session=db_session,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 22),
        channel="all",
    )
    assert [p.count for p in volume.points] == [0, 0, 0]

    intents = await analytics_service.get_top_intents(
        session=db_session,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 20),
        channel="all",
    )
    assert intents.points == []

    peak_hours = await analytics_service.get_peak_hours(
        session=db_session,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 20),
        channel="all",
    )
    assert len(peak_hours.points) == 24
    assert all(p.count == 0 for p in peak_hours.points)

    quality = await analytics_service.compute_quality_trend(
        session=db_session,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 21),
    )
    assert [p.value for p in quality.points] == [0.0, 0.0]

    lead = await analytics_service.compute_lead_conversion_trend(
        session=db_session,
        start_date=date(2026, 1, 20),
        end_date=date(2026, 1, 21),
    )
    assert [(p.count, p.rate_pct) for p in lead.points] == [(0, 0.0), (0, 0.0)]


@pytest.mark.asyncio
async def test_analytics_services_channel_filter_and_invalid_channel(db_session):
    await _seed(
        db_session,
        _chat(
            created_at=datetime(2026, 1, 25, 12, 0, 0),
            session_id="web-user",
            channel="web",
        ),
        _chat(
            created_at=datetime(2026, 1, 25, 13, 0, 0),
            session_id="wa-user",
            channel="whatsapp",
        ),
    )

    web_only = await analytics_service.get_message_volume_trend(
        session=db_session,
        start_date=date(2026, 1, 25),
        end_date=date(2026, 1, 25),
        channel="web",
    )
    wa_only = await analytics_service.get_message_volume_trend(
        session=db_session,
        start_date=date(2026, 1, 25),
        end_date=date(2026, 1, 25),
        channel="whatsapp",
    )
    assert [p.count for p in web_only.points] == [1]
    assert [p.count for p in wa_only.points] == [1]

    with pytest.raises(ValueError):
        await analytics_service.get_analytics_summary(
            session=db_session,
            start_date=date(2026, 1, 25),
            end_date=date(2026, 1, 25),
            channel="invalid-channel",
        )
