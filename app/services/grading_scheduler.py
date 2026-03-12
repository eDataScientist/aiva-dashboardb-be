from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.session import async_sessionmaker

from app.core import GRADING_BATCH_TIMEZONE, GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE
from app.core.config import Settings, get_settings
from app.db.database import get_session_factory
from app.models.grading_runs import GradingRun
from app.services.grading_batch import GradingBatchExecutionRequest, GradingBatchWindow
from app.services.grading_batch import build_default_batch_grader, execute_grading_batch
from app.schemas.grading_runs import GradingRunModeSchema, GradingRunTriggerTypeSchema
from app.schemas.grading_runs import GradingRunStatusSchema
from app.services.grading_runs import SqlAlchemyGradingRunStore, build_grading_run_store


_GST_ZONE = ZoneInfo(GRADING_BATCH_TIMEZONE)
_QUEUED_OR_RUNNING_STATUSES = (
    GradingRunStatusSchema.QUEUED.value,
    GradingRunStatusSchema.RUNNING.value,
)


@dataclass(frozen=True, slots=True)
class ScheduledGradingWindow:
    reference_date: date
    window: GradingBatchWindow


@dataclass(frozen=True, slots=True)
class GradingSchedulerHandle:
    stop_event: asyncio.Event
    task: asyncio.Task[None]


class ScheduledBatchRunner(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        request: GradingBatchExecutionRequest,
    ) -> None: ...


def build_previous_day_window(reference_date: date) -> ScheduledGradingWindow:
    previous_day = reference_date - timedelta(days=1)
    return ScheduledGradingWindow(
        reference_date=reference_date,
        window=GradingBatchWindow(
            start_date=previous_day,
            end_date=previous_day,
        ),
    )


def build_scheduled_batch_execution_request(
    reference_date: date,
) -> GradingBatchExecutionRequest:
    scheduled_window = build_previous_day_window(reference_date)
    return GradingBatchExecutionRequest(
        window=scheduled_window.window,
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED,
        run_mode=GradingRunModeSchema.DAILY,
        rerun_existing=False,
    )


def build_scheduled_batch_runner(
    settings: Settings | None = None,
) -> ScheduledBatchRunner:
    resolved_settings = settings or get_settings()
    grader = build_default_batch_grader(resolved_settings)

    async def run_scheduled_batch(
        session: AsyncSession,
        request: GradingBatchExecutionRequest,
    ) -> None:
        await execute_grading_batch(
            session,
            request,
            grader,
            settings=resolved_settings,
        )

    return run_scheduled_batch


async def recover_stale_grading_runs(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    now_utc: datetime | None = None,
    store: SqlAlchemyGradingRunStore | None = None,
) -> tuple[GradingRun, ...]:
    resolved_settings = settings or get_settings()
    resolved_store = store or build_grading_run_store()
    cutoff = _to_naive_utc(
        _resolve_now_utc(now_utc)
        - timedelta(minutes=resolved_settings.grading_batch_stale_run_timeout_minutes)
    )

    result = await session.execute(
        select(GradingRun)
        .where(
            GradingRun.status.in_(_QUEUED_OR_RUNNING_STATUSES),
            func.coalesce(GradingRun.started_at, GradingRun.created_at) <= cutoff,
        )
        .order_by(GradingRun.created_at.asc(), GradingRun.id.asc())
    )
    stale_runs = tuple(result.scalars().all())
    if not stale_runs:
        return ()

    for run in stale_runs:
        await resolved_store.update_run_status(
            session,
            run,
            GradingRunStatusSchema.FAILED,
            error_message=GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE,
        )

    await session.commit()
    return stale_runs


async def run_scheduled_batch_cycle(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    runner: ScheduledBatchRunner | None = None,
    now_utc: datetime | None = None,
    store: SqlAlchemyGradingRunStore | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    await recover_stale_grading_runs(
        session,
        settings=resolved_settings,
        now_utc=now_utc,
        store=store,
    )

    resolved_runner = runner or build_scheduled_batch_runner(resolved_settings)
    request = build_scheduled_batch_execution_request(
        reference_date=_resolve_now_utc(now_utc).astimezone(_GST_ZONE).date(),
    )
    await resolved_runner(session, request)


def seconds_until_next_scheduler_run(
    scheduler_hour_gst: int,
    *,
    now_utc: datetime | None = None,
) -> float:
    current_utc = _resolve_now_utc(now_utc)
    current_gst = current_utc.astimezone(_GST_ZONE)
    next_run_gst = datetime.combine(
        current_gst.date(),
        time(hour=scheduler_hour_gst),
        tzinfo=_GST_ZONE,
    )
    if current_gst >= next_run_gst:
        next_run_gst += timedelta(days=1)

    return max((next_run_gst.astimezone(timezone.utc) - current_utc).total_seconds(), 0.0)


async def run_grading_scheduler_loop(
    *,
    settings: Settings | None = None,
    stop_event: asyncio.Event | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    runner: ScheduledBatchRunner | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    if not resolved_settings.grading_batch_scheduler_enabled:
        return

    resolved_stop_event = stop_event or asyncio.Event()
    resolved_session_factory = session_factory or get_session_factory()

    async with resolved_session_factory() as session:
        await recover_stale_grading_runs(
            session,
            settings=resolved_settings,
        )

    while not resolved_stop_event.is_set():
        try:
            await asyncio.wait_for(
                resolved_stop_event.wait(),
                timeout=seconds_until_next_scheduler_run(
                    resolved_settings.grading_batch_scheduler_hour_gst
                ),
            )
            break
        except asyncio.TimeoutError:
            async with resolved_session_factory() as session:
                await run_scheduled_batch_cycle(
                    session,
                    settings=resolved_settings,
                    runner=runner,
                )


def start_grading_scheduler(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    runner: ScheduledBatchRunner | None = None,
) -> GradingSchedulerHandle | None:
    resolved_settings = settings or get_settings()
    if not resolved_settings.grading_batch_scheduler_enabled:
        return None

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_grading_scheduler_loop(
            settings=resolved_settings,
            stop_event=stop_event,
            session_factory=session_factory,
            runner=runner,
        )
    )
    return GradingSchedulerHandle(stop_event=stop_event, task=task)


async def stop_grading_scheduler(
    handle: GradingSchedulerHandle | None,
) -> None:
    if handle is None:
        return

    handle.stop_event.set()
    await handle.task


def _resolve_now_utc(now_utc: datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def _to_naive_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)
