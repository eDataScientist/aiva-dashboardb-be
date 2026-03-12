from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION
from app.models.grading_runs import GradingRunItem
from app.models.enums import IdentityType
from app.schemas.grading_runs import (
    GradingRunItemStatusSchema,
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerTypeSchema,
)
from app.services.grading_runs import (
    GradingRunCreateParams,
    GradingRunItemCreateParams,
    GradingRunItemRecordingError,
    GradingRunRuntimeSnapshot,
    GradingRunStateTransitionError,
    SqlAlchemyGradingRunStore,
    determine_terminal_run_status,
)


def _runtime_snapshot() -> GradingRunRuntimeSnapshot:
    return GradingRunRuntimeSnapshot(
        provider="mock",
        model=GRADING_DEFAULT_MODEL,
        prompt_version=GRADING_DEFAULT_PROMPT_VERSION,
    )


def _run_params(**overrides: object) -> GradingRunCreateParams:
    payload: dict[str, object] = {
        "trigger_type": GradingRunTriggerTypeSchema.MANUAL,
        "run_mode": GradingRunModeSchema.BACKFILL,
        "status": GradingRunStatusSchema.QUEUED,
        "target_start_date": date(2026, 3, 9),
        "target_end_date": date(2026, 3, 10),
        "rerun_existing": False,
        "runtime_snapshot": _runtime_snapshot(),
        "requested_by_account_id": None,
        "error_message": None,
    }
    payload.update(overrides)
    return GradingRunCreateParams(**payload)


@pytest.mark.asyncio
async def test_create_run_persists_runtime_snapshot_and_zeroed_counters(db_session) -> None:
    store = SqlAlchemyGradingRunStore()

    run = await store.create_run(db_session, _run_params())

    assert run.status == GradingRunStatusSchema.QUEUED.value
    assert run.trigger_type == GradingRunTriggerTypeSchema.MANUAL.value
    assert run.run_mode == GradingRunModeSchema.BACKFILL.value
    assert run.provider == "mock"
    assert run.model == GRADING_DEFAULT_MODEL
    assert run.prompt_version == GRADING_DEFAULT_PROMPT_VERSION
    assert run.candidate_count == 0
    assert run.attempted_count == 0
    assert run.success_count == 0
    assert run.skipped_existing_count == 0
    assert run.empty_transcript_count == 0
    assert run.provider_error_count == 0
    assert run.parse_error_count == 0
    assert run.started_at is None
    assert run.finished_at is None


@pytest.mark.asyncio
async def test_update_run_status_allows_queued_running_completed_flow(db_session) -> None:
    store = SqlAlchemyGradingRunStore()
    run = await store.create_run(db_session, _run_params())

    await store.update_run_status(db_session, run, GradingRunStatusSchema.RUNNING)
    started_at = run.started_at

    assert started_at is not None
    assert run.finished_at is None

    await store.update_run_status(db_session, run, GradingRunStatusSchema.COMPLETED)

    assert run.status == GradingRunStatusSchema.COMPLETED.value
    assert run.started_at == started_at
    assert run.finished_at is not None
    assert run.error_message is None


@pytest.mark.asyncio
async def test_update_run_status_rejects_invalid_transition(db_session) -> None:
    store = SqlAlchemyGradingRunStore()
    run = await store.create_run(db_session, _run_params())

    with pytest.raises(GradingRunStateTransitionError):
        await store.update_run_status(
            db_session,
            run,
            GradingRunStatusSchema.COMPLETED,
        )


@pytest.mark.asyncio
async def test_update_run_status_allows_queued_to_failed_with_error_message(
    db_session,
) -> None:
    store = SqlAlchemyGradingRunStore()
    run = await store.create_run(db_session, _run_params())

    await store.update_run_status(
        db_session,
        run,
        GradingRunStatusSchema.FAILED,
        error_message="  Advisory lock already held for the requested window.  ",
    )

    assert run.status == GradingRunStatusSchema.FAILED.value
    assert run.started_at is None
    assert run.finished_at is not None
    assert run.error_message == "Advisory lock already held for the requested window."


@pytest.mark.asyncio
async def test_create_run_item_records_success_and_updates_attempted_counters(
    db_session,
) -> None:
    store = SqlAlchemyGradingRunStore()
    run = await store.create_run(db_session, _run_params())
    await store.update_run_status(db_session, run, GradingRunStatusSchema.RUNNING)

    item = await store.create_run_item(
        db_session,
        run,
        GradingRunItemCreateParams(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000123",
            grade_date=date(2026, 3, 9),
            status=GradingRunItemStatusSchema.SUCCESS,
        ),
    )

    assert item.status == GradingRunItemStatusSchema.SUCCESS.value
    assert item.started_at is not None
    assert item.finished_at is not None
    assert run.candidate_count == 1
    assert run.attempted_count == 1
    assert run.success_count == 1
    assert run.skipped_existing_count == 0
    assert determine_terminal_run_status(run) is GradingRunStatusSchema.COMPLETED


@pytest.mark.asyncio
async def test_create_run_item_records_skip_and_failure_counters_with_bounded_details(
    db_session,
) -> None:
    store = SqlAlchemyGradingRunStore()
    run = await store.create_run(db_session, _run_params())
    await store.update_run_status(db_session, run, GradingRunStatusSchema.RUNNING)

    await store.create_run_item(
        db_session,
        run,
        GradingRunItemCreateParams(
            identity_type=IdentityType.EMAIL,
            conversation_identity="customer@example.com",
            grade_date=date(2026, 3, 9),
            status=GradingRunItemStatusSchema.SKIPPED_EXISTING,
        ),
    )
    item = await store.create_run_item(
        db_session,
        run,
        GradingRunItemCreateParams(
            identity_type=IdentityType.SESSION,
            conversation_identity="session-001",
            grade_date=date(2026, 3, 10),
            status=GradingRunItemStatusSchema.PARSE_ERROR,
            error_message=f"  {'x' * 600}  ",
            error_details=tuple(f" detail-{index} " for index in range(12)),
        ),
    )

    persisted_item = await db_session.scalar(
        select(GradingRunItem).where(GradingRunItem.id == item.id)
    )

    assert run.candidate_count == 2
    assert run.attempted_count == 1
    assert run.success_count == 0
    assert run.skipped_existing_count == 1
    assert run.parse_error_count == 1
    assert determine_terminal_run_status(run) is (
        GradingRunStatusSchema.COMPLETED_WITH_FAILURES
    )
    assert persisted_item is not None
    assert persisted_item.error_message == "x" * 500
    assert persisted_item.error_details == [f"detail-{index}" for index in range(10)]


@pytest.mark.asyncio
async def test_create_run_item_rejects_non_running_run(db_session) -> None:
    store = SqlAlchemyGradingRunStore()
    run = await store.create_run(db_session, _run_params())

    with pytest.raises(GradingRunItemRecordingError):
        await store.create_run_item(
            db_session,
            run,
            GradingRunItemCreateParams(
                identity_type=IdentityType.PHONE,
                conversation_identity="+971500000123",
                grade_date=date(2026, 3, 9),
                status=GradingRunItemStatusSchema.SUCCESS,
            ),
        )
