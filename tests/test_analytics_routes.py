from __future__ import annotations

from datetime import datetime

import pytest

from app.models.chats import ChatMessage


def _chat(
    *,
    created_at: datetime,
    session_id: str,
    direction: str = "inbound",
    channel: str = "web",
    intent: str | None = None,
    escalated: str | None = None,
) -> ChatMessage:
    return ChatMessage(
        created_at=created_at,
        session_id=session_id,
        direction=direction,
        channel=channel,
        intent=intent,
        escalated=escalated,
        message="route-test",
    )


async def _seed(db_session, *rows: ChatMessage) -> None:
    db_session.add_all(list(rows))
    await db_session.commit()


@pytest.mark.asyncio
async def test_analytics_routes_happy_path_returns_expected_payload_shapes(client, db_session):
    await _seed(
        db_session,
        _chat(
            created_at=datetime(2026, 1, 28, 12, 0, 0),
            session_id="r1",
            channel="web",
            direction="inbound",
            intent="Quote",
            escalated="false",
        ),
        _chat(
            created_at=datetime(2026, 1, 28, 13, 0, 0),
            session_id="r1",
            channel="web",
            direction="outbound",
            intent="Quote",
            escalated="false",
        ),
        _chat(
            created_at=datetime(2026, 1, 29, 14, 0, 0),
            session_id="r2",
            channel="whatsapp",
            direction="inbound",
            intent="New Contact Form Submitted",
            escalated="true",
        ),
    )

    common_params = "start_date=2026-01-28&end_date=2026-01-29&channel=all"

    summary = await client.get(f"/api/v1/analytics/summary?{common_params}")
    assert summary.status_code == 200
    summary_json = summary.json()
    assert summary_json["total_messages"] == 3
    assert summary_json["total_customers"] == 2
    assert summary_json["inbound_messages"] == 2
    assert summary_json["outbound_messages"] == 1
    assert summary_json["escalated_customers"] == 1
    assert "ai_quality_score" in summary_json

    volume = await client.get(f"/api/v1/analytics/message-volume-trend?{common_params}")
    assert volume.status_code == 200
    assert [p["count"] for p in volume.json()["points"]] == [2, 1]

    top_intents = await client.get(
        f"/api/v1/analytics/top-intents?{common_params}&limit=5"
    )
    assert top_intents.status_code == 200
    top_points = top_intents.json()["points"]
    assert top_points[0]["intent"] == "Quote"
    assert top_points[0]["count"] == 2

    peak_hours = await client.get(f"/api/v1/analytics/peak-hours?{common_params}")
    assert peak_hours.status_code == 200
    peak_points = peak_hours.json()["points"]
    assert len(peak_points) == 24
    assert sum(point["count"] for point in peak_points) == 3

    quality = await client.get(f"/api/v1/analytics/quality-trend?{common_params}")
    assert quality.status_code == 200
    assert len(quality.json()["points"]) == 2

    lead = await client.get(f"/api/v1/analytics/lead-conversion-trend?{common_params}")
    assert lead.status_code == 200
    assert len(lead.json()["points"]) == 2


@pytest.mark.asyncio
async def test_analytics_routes_edge_cases_empty_db_are_zero_safe(client):
    params = "start_date=2026-02-01&end_date=2026-02-02&channel=all"

    summary = await client.get(f"/api/v1/analytics/summary?{params}")
    assert summary.status_code == 200
    assert summary.json()["total_messages"] == 0
    assert summary.json()["total_customers"] == 0

    volume = await client.get(f"/api/v1/analytics/message-volume-trend?{params}")
    assert volume.status_code == 200
    assert [p["count"] for p in volume.json()["points"]] == [0, 0]

    top_intents = await client.get(f"/api/v1/analytics/top-intents?{params}")
    assert top_intents.status_code == 200
    assert top_intents.json()["points"] == []

    peak_hours = await client.get(f"/api/v1/analytics/peak-hours?{params}")
    assert peak_hours.status_code == 200
    assert len(peak_hours.json()["points"]) == 24


@pytest.mark.asyncio
async def test_analytics_routes_validation_errors(client):
    bad_range = await client.get(
        "/api/v1/analytics/summary?start_date=2026-02-03&end_date=2026-02-01"
    )
    assert bad_range.status_code == 422
    assert "start_date" in bad_range.text

    bad_channel = await client.get("/api/v1/analytics/message-volume-trend?channel=sms")
    assert bad_channel.status_code == 422

    bad_limit_low = await client.get("/api/v1/analytics/top-intents?limit=0")
    assert bad_limit_low.status_code == 422

    bad_limit_high = await client.get("/api/v1/analytics/top-intents?limit=100")
    assert bad_limit_high.status_code == 422
