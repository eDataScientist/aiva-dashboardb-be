from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.constants import GRADING_BATCH_TIMEZONE
from app.core.security import create_access_token
from app.models.account import Account
from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun
from app.schemas.grading_runs import (
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)

_GST = ZoneInfo(GRADING_BATCH_TIMEZONE)


def _gst_future_date() -> date:
    return datetime.now(tz=_GST).date() + timedelta(days=1)


async def _persist_account(
    db_session,
    *,
    email: str,
    role: str,
) -> Account:
    account = Account(
        email=email,
        password_hash="hashed-password",
        full_name="Test User",
        role=role,
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    return account


def _auth_headers(account: Account) -> dict[str, str]:
    token = create_access_token(
        subject=str(account.id),
        email=account.email,
        role=account.role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _persist_grade(
    db_session,
    *,
    phone_number: str,
    grade_date: date,
    intent_code: str = "policy_inquiry",
    relevancy_score: int = 7,
    accuracy_score: int = 7,
    completeness_score: int = 7,
    clarity_score: int = 7,
    tone_score: int = 7,
    repetition_score: int = 5,
    satisfaction_score: int = 7,
    frustration_score: int = 3,
    resolution: bool = True,
    loop_detected: bool = False,
    user_relevancy: bool = True,
    escalation_occurred: bool = False,
    escalation_type: str = "None",
) -> ConversationGrade:
    grade = ConversationGrade(
        phone_number=phone_number,
        grade_date=grade_date,
        identity_type=IdentityType.PHONE,
        conversation_identity=phone_number,
        intent_code=intent_code,
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


async def _persist_chat(
    db_session,
    *,
    conversation_identity: str,
    created_at: datetime,
    customer_name: str | None = None,
) -> ChatMessage:
    chat = ChatMessage(
        customer_phone=conversation_identity,
        customer_email_address=None,
        session_id=None,
        customer_name=customer_name,
        message="Test message",
        direction="inbound",
        channel="whatsapp",
        message_type="text",
        created_at=created_at,
    )
    db_session.add(chat)
    await db_session.flush()
    return chat


async def _persist_successful_run(db_session) -> GradingRun:
    run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.BACKFILL.value,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_start_date=date(2026, 3, 5),
        target_end_date=date(2026, 3, 5),
        rerun_existing=False,
        provider="mock",
        model="gpt-4o",
        prompt_version="v1",
        created_at=datetime(2026, 3, 5, 10, 0, 0),
        updated_at=datetime(2026, 3, 5, 10, 30, 0),
        finished_at=datetime(2026, 3, 5, 10, 30, 0),
    )
    db_session.add(run)
    await db_session.flush()
    return run


# ---------------------------------------------------------------------------
# Auth - all three dashboard endpoints require authentication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_agent_pulse_requires_auth(client):
    response = await client.get("/api/v1/grading/dashboard/agent-pulse")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"


@pytest.mark.asyncio
async def test_dashboard_correlations_requires_auth(client):
    response = await client.get("/api/v1/grading/dashboard/correlations")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_requires_auth(client):
    response = await client.get("/api/v1/grading/dashboard/daily-timeline")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"


# ---------------------------------------------------------------------------
# Auth - all three roles are allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_agent_pulse_allows_analyst(client, db_session):
    analyst = await _persist_account(
        db_session, email="analyst-dash-pulse@example.com", role="analyst"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/agent-pulse",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_correlations_allows_company_admin(client, db_session):
    admin = await _persist_account(
        db_session, email="cadmin-dash-corr@example.com", role="company_admin"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/correlations",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_allows_super_admin(client, db_session):
    super_admin = await _persist_account(
        db_session, email="sadmin-dash-timeline@example.com", role="super_admin"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/daily-timeline",
        params={"target_date": "2026-03-05"},
        headers=_auth_headers(super_admin),
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Validation - Agent Pulse and Correlations date window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_agent_pulse_rejects_inverted_window(client, db_session):
    analyst = await _persist_account(
        db_session, email="analyst-dash-inv@example.com", role="analyst"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/agent-pulse",
        params={"start_date": "2026-03-10", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    body = response.json()
    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"
    assert len(body["detail"]["details"]) > 0


@pytest.mark.asyncio
async def test_dashboard_correlations_rejects_future_end_date(client, db_session):
    analyst = await _persist_account(
        db_session, email="analyst-dash-future@example.com", role="analyst"
    )
    future_end = _gst_future_date().isoformat()
    response = await client.get(
        "/api/v1/grading/dashboard/correlations",
        params={"start_date": "2026-03-01", "end_date": future_end},
        headers=_auth_headers(analyst),
    )
    body = response.json()
    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"


# ---------------------------------------------------------------------------
# Validation - Daily Timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_rejects_future_target_date(client, db_session):
    analyst = await _persist_account(
        db_session, email="analyst-dash-tl-future@example.com", role="analyst"
    )
    future_date = _gst_future_date().isoformat()
    response = await client.get(
        "/api/v1/grading/dashboard/daily-timeline",
        params={"target_date": future_date},
        headers=_auth_headers(analyst),
    )
    body = response.json()
    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_rejects_over_max_worst_performers_limit(
    client, db_session
):
    analyst = await _persist_account(
        db_session, email="analyst-dash-tl-overmax@example.com", role="analyst"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/daily-timeline",
        params={"target_date": "2026-03-05", "worst_performers_limit": 51},
        headers=_auth_headers(analyst),
    )
    body = response.json()
    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_limit"
    assert len(body["detail"]["details"]) > 0


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_rejects_non_positive_worst_performers_limit(
    client, db_session
):
    analyst = await _persist_account(
        db_session, email="analyst-dash-tl-neg@example.com", role="analyst"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/daily-timeline",
        params={"target_date": "2026-03-05", "worst_performers_limit": 0},
        headers=_auth_headers(analyst),
    )
    body = response.json()
    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_limit"


# ---------------------------------------------------------------------------
# Empty state - Agent Pulse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_agent_pulse_empty_window_returns_zeros(client, db_session):
    admin = await _persist_account(
        db_session, email="sadmin-dash-pulse-empty@example.com", role="super_admin"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/agent-pulse",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 0
    assert body["overall_composite_score"] == 0.0
    assert body["dimension_averages"]["relevancy"] == 0.0
    assert body["health"]["resolution_rate_pct"] == 0.0
    assert body["freshness"]["latest_successful_run_id"] is None
    assert body["trend_points"] != []
    assert body["top_intents"] == []
    assert body["attention_signals"] == []


# ---------------------------------------------------------------------------
# Empty state - Correlations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_correlations_empty_window_returns_zero_filled(client, db_session):
    admin = await _persist_account(
        db_session, email="sadmin-dash-corr-empty@example.com", role="super_admin"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/correlations",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 0
    assert len(body["heatmap_cells"]) == 15
    assert all(cell["conversation_count"] == 0 for cell in body["heatmap_cells"])
    assert len(body["failure_funnel"]) == 5
    assert all(step["count"] == 0 for step in body["failure_funnel"])
    assert len(body["frustration_histogram"]) == 5
    assert all(bucket["count"] == 0 for bucket in body["frustration_histogram"])
    assert len(body["story_cards"]) == 4


# ---------------------------------------------------------------------------
# Empty state - Daily Timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_empty_day_returns_24_zero_buckets(client, db_session):
    admin = await _persist_account(
        db_session, email="sadmin-dash-tl-empty@example.com", role="super_admin"
    )
    response = await client.get(
        "/api/v1/grading/dashboard/daily-timeline",
        params={"target_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["target_date"] == "2026-03-05"
    assert len(body["hourly_buckets"]) == 24
    assert [b["hour"] for b in body["hourly_buckets"]] == list(range(24))
    assert all(b["conversation_volume"] == 0 for b in body["hourly_buckets"])
    assert body["best_hour"] is None
    assert body["worst_hour"] is None
    assert body["scatter_points"] == []
    assert body["worst_performers"] == []


# ---------------------------------------------------------------------------
# Populated state - Agent Pulse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_agent_pulse_returns_populated_payload(client, db_session):
    admin = await _persist_account(
        db_session, email="sadmin-dash-pulse-pop@example.com", role="super_admin"
    )
    await _persist_grade(
        db_session,
        phone_number="+971500100001",
        grade_date=date(2026, 3, 5),
        relevancy_score=8,
        accuracy_score=7,
        completeness_score=9,
        clarity_score=6,
        tone_score=8,
        satisfaction_score=8,
        frustration_score=2,
        resolution=True,
        loop_detected=False,
        escalation_type="None",
    )
    await _persist_successful_run(db_session)

    response = await client.get(
        "/api/v1/grading/dashboard/agent-pulse",
        params={"start_date": "2026-03-05", "end_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 1
    assert body["date_window"]["start_date"] == "2026-03-05"
    assert body["date_window"]["end_date"] == "2026-03-05"
    assert body["dimension_averages"]["relevancy"] == 8.0
    assert body["health"]["resolution_rate_pct"] == 100.0
    assert body["freshness"]["latest_successful_run_id"] is not None
    assert len(body["trend_points"]) == 1
    assert body["trend_points"][0]["date"] == "2026-03-05"
    assert len(body["escalation_breakdown"]) == 3


# ---------------------------------------------------------------------------
# Populated state - Correlations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_correlations_returns_populated_payload(client, db_session):
    admin = await _persist_account(
        db_session, email="sadmin-dash-corr-pop@example.com", role="super_admin"
    )
    await _persist_grade(
        db_session,
        phone_number="+971500100002",
        grade_date=date(2026, 3, 5),
        relevancy_score=3,
        accuracy_score=5,
        completeness_score=9,
        clarity_score=7,
        tone_score=8,
        satisfaction_score=6,
        frustration_score=7,
        resolution=False,
        loop_detected=True,
        escalation_type="Failure",
    )

    response = await client.get(
        "/api/v1/grading/dashboard/correlations",
        params={"start_date": "2026-03-05", "end_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 1
    assert len(body["heatmap_cells"]) == 15
    assert body["failure_funnel"][0]["step_key"] == "total"
    assert body["failure_funnel"][0]["count"] == 1
    assert len(body["frustration_histogram"]) == 5
    assert len(body["story_cards"]) == 4


# ---------------------------------------------------------------------------
# Populated state - Daily Timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_daily_timeline_returns_populated_payload(client, db_session):
    admin = await _persist_account(
        db_session, email="sadmin-dash-tl-pop@example.com", role="super_admin"
    )
    await _persist_grade(
        db_session,
        phone_number="+971500100003",
        grade_date=date(2026, 3, 5),
        relevancy_score=6,
        accuracy_score=6,
        completeness_score=6,
        clarity_score=6,
        tone_score=6,
        satisfaction_score=7,
        frustration_score=3,
        resolution=True,
        loop_detected=False,
        escalation_type="None",
        intent_code="complaint",
    )
    await _persist_chat(
        db_session,
        conversation_identity="+971500100003",
        created_at=datetime(2026, 3, 5, 8, 0, 0),
        customer_name="Test Customer",
    )

    response = await client.get(
        "/api/v1/grading/dashboard/daily-timeline",
        params={"target_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["target_date"] == "2026-03-05"
    assert len(body["hourly_buckets"]) == 24
    assert body["best_hour"] is not None
    assert body["worst_hour"] is not None
    assert len(body["scatter_points"]) == 1
    assert body["scatter_points"][0]["satisfaction_score"] == 7.0
    assert body["scatter_points"][0]["frustration_score"] == 3.0
    assert len(body["worst_performers"]) == 1
    assert body["worst_performers"][0]["relevancy_score"] == 6
    assert body["worst_performers"][0]["contact_label"] == "Test Customer"
    assert body["worst_performers"][0]["intent_code"] == "complaint"
