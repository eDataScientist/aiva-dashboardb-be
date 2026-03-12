from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.constants import GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE
from app.models.grading_runs import GradingRun
from app.schemas.grading_runs import GradingRunModeSchema, GradingRunStatusSchema
from app.schemas.grading_runs import GradingRunTriggerTypeSchema
from app.services.grading_scheduler import (
    recover_stale_grading_runs,
    run_scheduled_batch_cycle,
    start_grading_scheduler,
)


def _settings(**overrides):
    from app.core.config import Settings
    from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION

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
        "grading_batch_scheduler_enabled": True,
        "grading_batch_scheduler_hour_gst": 1,
        "grading_batch_max_backfill_days": 31,
        "grading_batch_stale_run_timeout_minutes": 180,
        "grading_batch_allow_mock_provider_runs": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_recover_stale_grading_runs_marks_old_queued_and_running_runs_failed(
    db_session,
):
    stale_created_at = datetime(2026, 3, 11, 0, 0, 0)
    stale_started_at = datetime(2026, 3, 11, 1, 0, 0)
    fresh_started_at = datetime(2026, 3, 12, 11, 30, 0)

    queued_run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.DAILY.value,
        status=GradingRunStatusSchema.QUEUED.value,
        target_start_date=date(2026, 3, 10),
        target_end_date=date(2026, 3, 10),
        rerun_existing=False,
        provider="mock",
        model="mock-grade-v1",
        prompt_version="v1",
        created_at=stale_created_at,
        updated_at=stale_created_at,
    )
    running_run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.DAILY.value,
        status=GradingRunStatusSchema.RUNNING.value,
        target_start_date=date(2026, 3, 11),
        target_end_date=date(2026, 3, 11),
        rerun_existing=False,
        provider="mock",
        model="mock-grade-v1",
        prompt_version="v1",
        started_at=stale_started_at,
        created_at=stale_created_at,
        updated_at=stale_created_at,
    )
    fresh_run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.DAILY.value,
        status=GradingRunStatusSchema.RUNNING.value,
        target_start_date=date(2026, 3, 12),
        target_end_date=date(2026, 3, 12),
        rerun_existing=False,
        provider="mock",
        model="mock-grade-v1",
        prompt_version="v1",
        started_at=fresh_started_at,
        created_at=fresh_started_at,
        updated_at=fresh_started_at,
    )
    db_session.add_all([queued_run, running_run, fresh_run])
    await db_session.flush()

    recovered = await recover_stale_grading_runs(
        db_session,
        settings=_settings(grading_batch_stale_run_timeout_minutes=180),
        now_utc=datetime(2026, 3, 12, 12, 0, 0, tzinfo=timezone.utc),
    )

    await db_session.refresh(queued_run)
    await db_session.refresh(running_run)
    await db_session.refresh(fresh_run)

    assert {run.id for run in recovered} == {queued_run.id, running_run.id}
    assert queued_run.status == GradingRunStatusSchema.FAILED.value
    assert running_run.status == GradingRunStatusSchema.FAILED.value
    assert fresh_run.status == GradingRunStatusSchema.RUNNING.value
    assert queued_run.error_message == GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE
    assert running_run.error_message == GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE
    assert queued_run.finished_at is not None
    assert running_run.finished_at is not None


@pytest.mark.asyncio
async def test_run_scheduled_batch_cycle_recovers_stale_runs_and_executes_previous_day_window(
    db_session,
):
    stale_started_at = datetime(2026, 3, 11, 1, 0, 0)
    stale_run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.DAILY.value,
        status=GradingRunStatusSchema.RUNNING.value,
        target_start_date=date(2026, 3, 11),
        target_end_date=date(2026, 3, 11),
        rerun_existing=False,
        provider="mock",
        model="mock-grade-v1",
        prompt_version="v1",
        started_at=stale_started_at,
        created_at=stale_started_at,
        updated_at=stale_started_at,
    )
    db_session.add(stale_run)
    await db_session.flush()

    runner = AsyncMock()

    await run_scheduled_batch_cycle(
        db_session,
        settings=_settings(),
        runner=runner,
        now_utc=datetime(2026, 3, 12, 3, 30, 0, tzinfo=timezone.utc),
    )

    await db_session.refresh(stale_run)

    assert stale_run.status == GradingRunStatusSchema.FAILED.value
    assert stale_run.error_message == GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE
    assert runner.await_count == 1
    request = runner.await_args.args[1]
    assert request.trigger_type == GradingRunTriggerTypeSchema.SCHEDULED
    assert request.run_mode == GradingRunModeSchema.DAILY
    assert request.rerun_existing is False
    assert request.window.start_date == date(2026, 3, 11)
    assert request.window.end_date == date(2026, 3, 11)


def test_start_grading_scheduler_returns_none_when_disabled():
    handle = start_grading_scheduler(
        settings=_settings(grading_batch_scheduler_enabled=False),
    )

    assert handle is None
