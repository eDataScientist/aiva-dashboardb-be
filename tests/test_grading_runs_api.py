from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.account import Account
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun, GradingRunItem
from app.schemas.grading_runs import (
    GradingRunItemStatusSchema,
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


async def _persist_run(
    db_session,
    *,
    status: str,
    trigger_type: str = GradingRunTriggerTypeSchema.MANUAL.value,
    run_mode: str = GradingRunModeSchema.BACKFILL.value,
    start_date: date = date(2026, 3, 5),
    end_date: date = date(2026, 3, 5),
    requested_by_account_id=None,
    created_at: datetime | None = None,
) -> GradingRun:
    run = GradingRun(
        trigger_type=trigger_type,
        run_mode=run_mode,
        status=status,
        target_start_date=start_date,
        target_end_date=end_date,
        rerun_existing=run_mode == GradingRunModeSchema.RERUN.value,
        provider="mock",
        model="gpt-4o",
        prompt_version="v1",
        requested_by_account_id=requested_by_account_id,
        created_at=created_at or datetime(2026, 3, 12, 10, 0, 0),
        updated_at=created_at or datetime(2026, 3, 12, 10, 0, 0),
    )
    db_session.add(run)
    await db_session.flush()
    return run


async def _persist_run_item(
    db_session,
    run: GradingRun,
    *,
    conversation_identity: str,
    status: str,
) -> GradingRunItem:
    item = GradingRunItem(
        run_id=run.id,
        identity_type=IdentityType.PHONE.value,
        conversation_identity=conversation_identity,
        grade_date=run.target_start_date,
        status=status,
        created_at=datetime(2026, 3, 12, 10, 0, 0),
        updated_at=datetime(2026, 3, 12, 10, 0, 0),
    )
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.mark.asyncio
async def test_trigger_grading_run_requires_auth(client):
    response = await client.post(
        "/api/v1/grading/runs",
        json={"grade_date": "2026-03-05"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"


@pytest.mark.asyncio
async def test_trigger_grading_run_rejects_non_super_admin(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst@example.com",
        role="analyst",
    )

    response = await client.post(
        "/api/v1/grading/runs",
        json={"grade_date": "2026-03-05"},
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "execution_not_allowed"


@pytest.mark.asyncio
async def test_trigger_grading_run_returns_accepted_and_queues_background_execution(
    client,
    db_session,
):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    with patch(
        "app.api.routes.grading_runs.run_grading_batch_in_background",
        new_callable=AsyncMock,
    ) as mock_background_runner:
        response = await client.post(
            "/api/v1/grading/runs",
            json={"grade_date": "2026-03-05", "rerun_existing": True},
            headers=_auth_headers(super_admin),
        )

    body = response.json()
    persisted_run = await db_session.scalar(
        select(GradingRun).where(GradingRun.id == UUID(body["run"]["id"]))
    )

    assert response.status_code == 202
    assert body["run"]["status"] == "queued"
    assert body["run"]["trigger_type"] == "manual"
    assert body["run"]["run_mode"] == "rerun"
    assert body["run"]["requested_by_account_id"] == str(super_admin.id)
    assert persisted_run is not None
    assert persisted_run.status == GradingRunStatusSchema.QUEUED.value
    mock_background_runner.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_grading_run_returns_validation_error_for_invalid_window(
    client,
    db_session,
):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    response = await client.post(
        "/api/v1/grading/runs",
        json={"start_date": "2026-01-01", "end_date": "2026-02-15"},
        headers=_auth_headers(super_admin),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_date_window"
    assert "Manual grading run request is invalid." == detail["message"]
    assert detail["details"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_detail"),
    [
        (
            {
                "grade_date": "2026-03-05",
                "start_date": "2026-03-01",
                "end_date": "2026-03-05",
            },
            "grade_date cannot be combined with start_date or end_date.",
        ),
        (
            {"start_date": "2026-03-01"},
            "start_date and end_date must be provided together.",
        ),
    ],
)
async def test_trigger_grading_run_returns_custom_validation_error_for_schema_level_invalid_payloads(
    client,
    db_session,
    payload,
    expected_detail,
):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    response = await client.post(
        "/api/v1/grading/runs",
        json=payload,
        headers=_auth_headers(super_admin),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_date_window"
    assert detail["message"] == "Manual grading run request is invalid."
    assert expected_detail in detail["details"]


@pytest.mark.asyncio
async def test_trigger_grading_run_returns_conflict_for_duplicate_active_window(
    client,
    db_session,
):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.RUNNING.value,
        requested_by_account_id=super_admin.id,
    )

    response = await client.post(
        "/api/v1/grading/runs",
        json={"grade_date": "2026-03-05"},
        headers=_auth_headers(super_admin),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "duplicate_active_window"


@pytest.mark.asyncio
async def test_list_grading_runs_requires_super_admin(client, db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst@example.com",
        role="analyst",
    )

    response = await client.get(
        "/api/v1/grading/runs",
        headers=_auth_headers(analyst),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "execution_not_allowed"


@pytest.mark.asyncio
async def test_list_grading_runs_returns_custom_validation_error_for_invalid_query(
    client,
    db_session,
):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    response = await client.get(
        "/api/v1/grading/runs?target_start_date=2026-03-06&target_end_date=2026-03-05",
        headers=_auth_headers(super_admin),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_date_window"
    assert detail["message"] == "Grading run history request is invalid."
    assert (
        "target_start_date must be less than or equal to target_end_date."
        in detail["details"]
    )


@pytest.mark.asyncio
async def test_list_grading_runs_returns_history_payload(client, db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )
    older_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        requested_by_account_id=super_admin.id,
        created_at=datetime(2026, 3, 12, 8, 0, 0),
    )
    newer_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.FAILED.value,
        requested_by_account_id=super_admin.id,
        created_at=datetime(2026, 3, 12, 9, 0, 0),
    )

    response = await client.get(
        "/api/v1/grading/runs?limit=10&offset=0",
        headers=_auth_headers(super_admin),
    )

    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [
        str(newer_run.id),
        str(older_run.id),
    ]


@pytest.mark.asyncio
async def test_get_grading_run_detail_returns_run_and_items(client, db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )
    run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED_WITH_FAILURES.value,
        requested_by_account_id=super_admin.id,
    )
    await _persist_run_item(
        db_session,
        run,
        conversation_identity="+971500000002",
        status=GradingRunItemStatusSchema.PROVIDER_ERROR.value,
    )
    await _persist_run_item(
        db_session,
        run,
        conversation_identity="+971500000001",
        status=GradingRunItemStatusSchema.SUCCESS.value,
    )

    response = await client.get(
        f"/api/v1/grading/runs/{run.id}",
        headers=_auth_headers(super_admin),
    )

    body = response.json()

    assert response.status_code == 200
    assert body["run"]["id"] == str(run.id)
    assert [item["conversation_identity"] for item in body["items"]] == [
        "+971500000001",
        "+971500000002",
    ]


@pytest.mark.asyncio
async def test_get_grading_run_detail_returns_not_found_for_unknown_id(client, db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    response = await client.get(
        "/api/v1/grading/runs/8f7bfbf2-3f3d-4a57-b7b0-1b040216b7cc",
        headers=_auth_headers(super_admin),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "run_not_found"
