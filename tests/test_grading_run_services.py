from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION
from app.models.account import Account
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun, GradingRunItem
from app.schemas.grading_runs import (
    GradingRunItemStatusSchema,
    GradingRunListQuery,
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerRequest,
    GradingRunTriggerTypeSchema,
)
from app.services.grading_batch import prepare_manual_grading_run
from app.services.grading_runs import (
    GradingRunConflictError,
    GradingRunNotFoundError,
    GradingRunPermissionError,
    GradingRunValidationError,
    get_grading_run_history_detail,
    list_grading_run_history,
)


def _settings(**overrides) -> Settings:
    defaults = {
        "database_url": "sqlite:///tests.db",
        "auth_jwt_secret": "x" * 32,
        "auth_jwt_algorithm": "HS256",
        "auth_access_token_expire_minutes": 60,
        "grading_provider": "mock",
        "grading_model": GRADING_DEFAULT_MODEL,
        "grading_request_timeout_seconds": 5,
        "grading_max_retries": 1,
        "grading_prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
        "grading_batch_max_backfill_days": 31,
    }
    defaults.update(overrides)
    return Settings(**defaults)


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
        model=GRADING_DEFAULT_MODEL,
        prompt_version=GRADING_DEFAULT_PROMPT_VERSION,
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
    grade_date: date = date(2026, 3, 5),
) -> GradingRunItem:
    item = GradingRunItem(
        run_id=run.id,
        identity_type=IdentityType.PHONE.value,
        conversation_identity=conversation_identity,
        grade_date=grade_date,
        status=status,
        created_at=datetime(2026, 3, 12, 10, 0, 0),
        updated_at=datetime(2026, 3, 12, 10, 0, 0),
    )
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.mark.asyncio
async def test_prepare_manual_grading_run_rejects_non_super_admin(db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst@example.com",
        role="analyst",
    )

    with pytest.raises(GradingRunPermissionError):
        await prepare_manual_grading_run(
            db_session,
            current_account=analyst,
            trigger_request=GradingRunTriggerRequest(grade_date=date(2026, 3, 5)),
            settings=_settings(),
        )


@pytest.mark.asyncio
async def test_prepare_manual_grading_run_rejects_invalid_window(db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    with pytest.raises(GradingRunValidationError) as exc_info:
        await prepare_manual_grading_run(
            db_session,
            current_account=super_admin,
            trigger_request=GradingRunTriggerRequest(
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 5),
            ),
            settings=_settings(grading_batch_max_backfill_days=3),
        )

    assert exc_info.value.message == "Manual grading run request is invalid."
    assert exc_info.value.details
    assert "exceeds maximum allowed backfill" in exc_info.value.details[0]


@pytest.mark.asyncio
async def test_prepare_manual_grading_run_rejects_duplicate_active_window(db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )
    await _persist_run(
        db_session,
        status=GradingRunStatusSchema.RUNNING.value,
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 5),
        requested_by_account_id=super_admin.id,
    )

    with pytest.raises(GradingRunConflictError) as exc_info:
        await prepare_manual_grading_run(
            db_session,
            current_account=super_admin,
            trigger_request=GradingRunTriggerRequest(grade_date=date(2026, 3, 5)),
            settings=_settings(),
        )

    assert str(exc_info.value) == (
        "A grading run is already active for the requested date window."
    )


@pytest.mark.asyncio
async def test_prepare_manual_grading_run_creates_queued_run_and_request(db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    response, execution_request = await prepare_manual_grading_run(
        db_session,
        current_account=super_admin,
        trigger_request=GradingRunTriggerRequest(
            grade_date=date(2026, 3, 5),
            rerun_existing=True,
        ),
        settings=_settings(),
    )

    persisted_run = await db_session.scalar(
        select(GradingRun).where(GradingRun.id == response.run.id)
    )

    assert persisted_run is not None
    assert response.run.status == GradingRunStatusSchema.QUEUED
    assert response.run.run_mode == GradingRunModeSchema.RERUN
    assert response.run.requested_by_account_id == super_admin.id
    assert execution_request.window.start_date == date(2026, 3, 5)
    assert execution_request.window.end_date == date(2026, 3, 5)
    assert execution_request.requested_by_account_id == super_admin.id
    assert persisted_run.status == GradingRunStatusSchema.QUEUED.value


@pytest.mark.asyncio
async def test_list_grading_run_history_requires_super_admin(db_session):
    analyst = await _persist_account(
        db_session,
        email="analyst@example.com",
        role="analyst",
    )

    with pytest.raises(GradingRunPermissionError):
        await list_grading_run_history(
            db_session,
            current_account=analyst,
            filters=GradingRunListQuery(limit=20, offset=0),
        )


@pytest.mark.asyncio
async def test_list_grading_run_history_returns_paginated_runs(db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )
    older_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.COMPLETED.value,
        created_at=datetime(2026, 3, 12, 8, 0, 0),
        requested_by_account_id=super_admin.id,
    )
    newer_run = await _persist_run(
        db_session,
        status=GradingRunStatusSchema.FAILED.value,
        created_at=datetime(2026, 3, 12, 9, 0, 0),
        requested_by_account_id=super_admin.id,
    )

    response = await list_grading_run_history(
        db_session,
        current_account=super_admin,
        filters=GradingRunListQuery(limit=10, offset=0),
    )

    assert response.total == 2
    assert [item.id for item in response.items] == [newer_run.id, older_run.id]


@pytest.mark.asyncio
async def test_get_grading_run_history_detail_returns_run_and_items(db_session):
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

    response = await get_grading_run_history_detail(
        db_session,
        current_account=super_admin,
        run_id=run.id,
    )

    assert response.run.id == run.id
    assert [item.conversation_identity for item in response.items] == [
        "+971500000001",
        "+971500000002",
    ]
    assert [item.status for item in response.items] == [
        GradingRunItemStatusSchema.SUCCESS,
        GradingRunItemStatusSchema.PROVIDER_ERROR,
    ]


@pytest.mark.asyncio
async def test_get_grading_run_history_detail_raises_for_unknown_run(db_session):
    super_admin = await _persist_account(
        db_session,
        email="super-admin@example.com",
        role="super_admin",
    )

    with pytest.raises(GradingRunNotFoundError):
        await get_grading_run_history_detail(
            db_session,
            current_account=super_admin,
            run_id=UUID("8f7bfbf2-3f3d-4a57-b7b0-1b040216b7cc"),
        )
