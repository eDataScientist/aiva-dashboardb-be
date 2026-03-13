from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.constants import GRADING_BATCH_TIMEZONE
from app.core.security import create_access_token

_GST = ZoneInfo(GRADING_BATCH_TIMEZONE)


def _gst_future_date() -> date:
    """Return a date that is always strictly after the previous GST day (i.e., today or later in GST)."""
    return datetime.now(tz=_GST).date() + timedelta(days=1)
from app.models.account import Account
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun
from app.schemas.grading_runs import (
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)


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
    relevancy_score: int = 8,
    accuracy_score: int = 8,
    completeness_score: int = 8,
    clarity_score: int = 8,
    tone_score: int = 8,
    repetition_score: int = 8,
    satisfaction_score: int = 8,
    frustration_score: int = 3,
    resolution: bool | None = True,
    loop_detected: bool | None = False,
    user_relevancy: bool | None = True,
    escalation_occurred: bool | None = False,
    escalation_type: str | None = None,
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
# Summary endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_summary_requires_auth(client):
    response = await client.get("/api/v1/grading/metrics/summary")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"


@pytest.mark.asyncio
async def test_metrics_summary_allows_analyst_role(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-summary@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/summary",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_summary_allows_company_admin_role(client, db_session):
    admin = await _persist_account(
        db_session,
        email="cadmin-summary@example.com",
        role="company_admin",
    )
    response = await client.get(
        "/api/v1/grading/metrics/summary",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_summary_empty_window_returns_zeros(client, db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-summary-empty@example.com",
        role="super_admin",
    )
    response = await client.get(
        "/api/v1/grading/metrics/summary",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(super_admin),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 0
    assert body["average_scores"]["relevancy"] == 0.0
    assert body["outcome_rates"]["resolution_rate_pct"] == 0.0
    assert body["freshness"]["latest_successful_run_id"] is None


@pytest.mark.asyncio
async def test_metrics_summary_returns_populated_data(client, db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-summary-populated@example.com",
        role="super_admin",
    )
    await _persist_grade(
        db_session,
        phone_number="+1555000001",
        grade_date=date(2026, 3, 5),
        resolution=True,
        loop_detected=False,
        user_relevancy=True,
        escalation_occurred=False,
    )
    await _persist_successful_run(db_session)

    response = await client.get(
        "/api/v1/grading/metrics/summary",
        params={"start_date": "2026-03-05", "end_date": "2026-03-05"},
        headers=_auth_headers(super_admin),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 1
    assert body["average_scores"]["relevancy"] == 8.0
    assert body["outcome_rates"]["resolution_rate_pct"] == 100.0
    assert body["freshness"]["latest_successful_run_id"] is not None
    assert body["date_window"]["start_date"] == "2026-03-05"
    assert body["date_window"]["end_date"] == "2026-03-05"


@pytest.mark.asyncio
async def test_metrics_summary_rejects_inverted_date_window(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-inv-window@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/summary",
        params={"start_date": "2026-03-10", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"
    assert len(body["detail"]["details"]) > 0


@pytest.mark.asyncio
async def test_metrics_summary_rejects_future_end_date(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-future-date@example.com",
        role="analyst",
    )
    future_end = _gst_future_date().isoformat()
    response = await client.get(
        "/api/v1/grading/metrics/summary",
        params={"start_date": "2026-03-01", "end_date": future_end},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"


# ---------------------------------------------------------------------------
# Score trends endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_trends_requires_auth(client):
    response = await client.get("/api/v1/grading/metrics/score-trends")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_score_trends_returns_zero_filled_for_empty_window(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-score-empty@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/score-trends",
        params={"start_date": "2026-03-01", "end_date": "2026-03-03"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert len(body["points"]) == 3
    assert body["points"][0]["relevancy"] == 0.0
    assert body["date_window"]["start_date"] == "2026-03-01"
    assert body["date_window"]["end_date"] == "2026-03-03"


@pytest.mark.asyncio
async def test_score_trends_rejects_invalid_window(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-score-inv@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/score-trends",
        params={"start_date": "2026-03-10", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_date_window"


# ---------------------------------------------------------------------------
# Outcome trends endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outcome_trends_requires_auth(client):
    response = await client.get("/api/v1/grading/metrics/outcome-trends")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_outcome_trends_returns_zero_filled_for_empty_window(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-outcome-empty@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/outcome-trends",
        params={"start_date": "2026-03-01", "end_date": "2026-03-02"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert len(body["points"]) == 2
    assert body["points"][0]["resolution_rate_pct"] == 0.0


# ---------------------------------------------------------------------------
# Intent distribution endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intents_distribution_requires_auth(client):
    response = await client.get("/api/v1/grading/metrics/intents/distribution")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_intents_distribution_returns_all_canonical_codes(client, db_session):
    from app.core.constants import INTENT_CODES

    analyst = await _persist_account(
        db_session,
        email="analyst-dist@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/intents/distribution",
        params={"start_date": "2026-03-01", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 0
    returned_codes = {item["intent_code"] for item in body["items"]}
    assert returned_codes == set(INTENT_CODES)


@pytest.mark.asyncio
async def test_intents_distribution_returns_populated_counts(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-dist-populated@example.com",
        role="analyst",
    )
    await _persist_grade(
        db_session,
        phone_number="+1555000010",
        grade_date=date(2026, 3, 5),
        intent_code="policy_inquiry",
    )

    response = await client.get(
        "/api/v1/grading/metrics/intents/distribution",
        params={"start_date": "2026-03-05", "end_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total_graded_customer_days"] == 1
    policy_item = next(
        item for item in body["items"] if item["intent_code"] == "policy_inquiry"
    )
    assert policy_item["count"] == 1
    assert policy_item["share_pct"] == 100.0


# ---------------------------------------------------------------------------
# Intent trend endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intents_trend_requires_auth(client):
    response = await client.get("/api/v1/grading/metrics/intents/trend")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_intents_trend_rejects_invalid_intent_code(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-trend-invalid@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/intents/trend",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
            "intent_codes": "not_a_real_code",
        },
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_intent_filter"


@pytest.mark.asyncio
async def test_intents_trend_returns_zero_filled_for_empty_window(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst-trend-empty@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/intents/trend",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-02",
            "intent_codes": "policy_inquiry",
        },
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert len(body["series"]) == 1
    series = body["series"][0]
    assert series["intent_code"] == "policy_inquiry"
    assert len(series["points"]) == 2
    assert all(p["count"] == 0 for p in series["points"])


@pytest.mark.asyncio
async def test_intents_trend_returns_all_intents_when_no_filter(client, db_session):
    from app.core.constants import INTENT_CODES

    analyst = await _persist_account(
        db_session,
        email="analyst-trend-all@example.com",
        role="analyst",
    )
    response = await client.get(
        "/api/v1/grading/metrics/intents/trend",
        params={"start_date": "2026-03-01", "end_date": "2026-03-01"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert len(body["series"]) == len(INTENT_CODES)
