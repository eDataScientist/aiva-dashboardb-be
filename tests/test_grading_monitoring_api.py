from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

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
from app.services.conversations import encode_conversation_key


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
    loop_detected: bool | None = None,
    satisfaction_score: int | None = None,
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
        loop_detected=loop_detected,
        satisfaction_score=satisfaction_score,
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
        channel="whatsapp",
        message_type="text",
        created_at=created_at,
    )
    db_session.add(chat)
    await db_session.flush()
    return chat


async def _persist_successful_run(
    db_session,
    *,
    target_end_date: date,
) -> GradingRun:
    run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.BACKFILL.value,
        status=GradingRunStatusSchema.COMPLETED.value,
        target_start_date=target_end_date,
        target_end_date=target_end_date,
        rerun_existing=False,
        provider="mock",
        model="mock-grade-v1",
        prompt_version="v1",
        created_at=datetime(2026, 3, 12, 8, 0, 0),
        updated_at=datetime(2026, 3, 12, 8, 15, 0),
        finished_at=datetime(2026, 3, 12, 8, 15, 0),
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest.mark.asyncio
async def test_monitoring_list_requires_auth(client) -> None:
    response = await client.get("/api/v1/monitoring/conversations")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"


@pytest.mark.asyncio
async def test_monitoring_list_allows_company_admin_and_returns_empty_state_with_freshness(
    client,
    db_session,
) -> None:
    company_admin = await _persist_account(
        db_session,
        email="monitoring-admin@example.com",
        role="company_admin",
    )
    successful_run = await _persist_successful_run(
        db_session,
        target_end_date=date(2026, 3, 10),
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={"start_date": "2026-03-11", "end_date": "2026-03-11"},
        headers=_auth_headers(company_admin),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 0
    assert body["items"] == []
    assert body["freshness"]["latest_successful_run_id"] == str(successful_run.id)
    assert body["date_window"]["start_date"] == "2026-03-11"
    assert body["date_window"]["end_date"] == "2026-03-11"


@pytest.mark.asyncio
async def test_monitoring_list_returns_filtered_sorted_rows(client, db_session) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-analyst@example.com",
        role="analyst",
    )
    await _persist_grade(
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
    await _persist_grade(
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
    high_accuracy = await _persist_grade(
        db_session,
        conversation_identity="+971500000012",
        grade_date=date(2026, 3, 11),
        resolution=False,
        escalation_type="Failure",
        frustration_score=9,
        accuracy_score=3,
        intent_code="complaint",
        intent_label="Complaint",
    )
    low_accuracy = await _persist_grade(
        db_session,
        conversation_identity="+971500000013",
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
        conversation_identity=high_accuracy.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 10, 30, 0),
        message="High accuracy matching chat",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=low_accuracy.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 11, 0, 0),
        message="Low accuracy matching chat",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params=[
            ("start_date", "2026-03-11"),
            ("end_date", "2026-03-11"),
            ("resolution", "false"),
            ("escalation_types", "Failure"),
            ("frustration_min", "7"),
            ("accuracy_max", "3"),
            ("intent_codes", "complaint"),
            ("sort_by", "accuracy_score"),
            ("sort_direction", "asc"),
        ],
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2
    assert [item["grade_id"] for item in body["items"]] == [
        str(low_accuracy.id),
        str(high_accuracy.id),
    ]
    assert body["items"][0]["latest_message_preview"] == "Low accuracy matching chat"
    assert body["items"][1]["latest_message_preview"] == "High accuracy matching chat"


@pytest.mark.asyncio
async def test_monitoring_list_rejects_invalid_intent_filter(client, db_session) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-invalid-intent@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={
            "start_date": "2026-03-11",
            "end_date": "2026-03-11",
            "intent_codes": "not-a-real-intent",
        },
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_intent_filter"


@pytest.mark.asyncio
async def test_monitoring_list_rejects_invalid_date_window(client, db_session) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-invalid-window@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={
            "start_date": "2026-03-12",
            "end_date": "2026-03-11",
        },
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_date_window"


@pytest.mark.asyncio
async def test_monitoring_list_rejects_malformed_date_input_with_monitoring_envelope(
    client,
    db_session,
) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-malformed-date@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={"start_date": "not-a-date"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"
    assert isinstance(body["detail"]["details"], list)
    assert body["detail"]["details"]


@pytest.mark.asyncio
async def test_monitoring_list_rejects_malformed_numeric_input_with_monitoring_envelope(
    client,
    db_session,
) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-malformed-int@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={"frustration_min": "nope"},
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["code"] == "invalid_date_window"
    assert isinstance(body["detail"]["details"], list)
    assert body["detail"]["details"]


@pytest.mark.asyncio
async def test_monitoring_list_rejects_invalid_escalation_filter(
    client,
    db_session,
) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-invalid-escalation@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={
            "start_date": "2026-03-11",
            "end_date": "2026-03-11",
            "escalation_types": "Broken",
        },
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_escalation_filter"


@pytest.mark.asyncio
async def test_monitoring_list_rejects_invalid_sort_query(client, db_session) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-invalid-sort@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations",
        params={
            "start_date": "2026-03-11",
            "end_date": "2026-03-11",
            "sort_by": "grade_date",
        },
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_sort"


@pytest.mark.asyncio
async def test_monitoring_detail_returns_detail_payload(client, db_session) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-detail@example.com",
        role="analyst",
    )
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
        loop_detected=True,
        satisfaction_score=2,
    )
    history_grade = await _persist_grade(
        db_session,
        conversation_identity="+971500000030",
        grade_date=date(2026, 3, 10),
        resolution=False,
        escalation_type="Natural",
        frustration_score=7,
        accuracy_score=6,
        intent_code="complaint",
        intent_label="Complaint",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 9, 0, 0),
        message="Customer asks for human support.",
        customer_name="Jane Customer",
        direction="inbound",
    )
    await _persist_chat(
        db_session,
        identity_type=IdentityType.PHONE,
        conversation_identity=grade.conversation_identity or "",
        created_at=datetime(2026, 3, 11, 9, 2, 0),
        message="Escalating this conversation now.",
        customer_name="Jane Customer",
        direction="outbound",
    )

    response = await client.get(
        f"/api/v1/monitoring/conversations/{grade.id}",
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["detail"]["grade_id"] == str(grade.id)
    assert body["detail"]["conversation_key"] == encode_conversation_key(
        grade.conversation_identity or ""
    )
    assert body["detail"]["contact_name"] == "Jane Customer"
    assert [item["grade_id"] for item in body["detail"]["recent_history"]] == [
        str(history_grade.id)
    ]
    assert [message["role"] for message in body["detail"]["transcript"]] == [
        "user",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_monitoring_detail_returns_not_found_for_unknown_grade(
    client,
    db_session,
) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-missing-detail@example.com",
        role="analyst",
    )

    response = await client.get(
        f"/api/v1/monitoring/conversations/{uuid4()}",
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "grade_not_found"


@pytest.mark.asyncio
async def test_monitoring_detail_rejects_malformed_uuid_with_monitoring_envelope(
    client,
    db_session,
) -> None:
    analyst = await _persist_account(
        db_session,
        email="monitoring-malformed-uuid@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/monitoring/conversations/not-a-uuid",
        headers=_auth_headers(analyst),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["code"] == "grade_not_found"
    assert isinstance(body["detail"]["details"], list)
    assert body["detail"]["details"]
