from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.database import get_session_factory
from app.models.account import Account
from app.models.conversation_grades import ConversationGrade
from app.models.grading_runs import GradingRun
from app.schemas.grading_runs import (
    GradingRunItemStatusSchema,
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerRequest,
    GradingRunTriggerTypeSchema,
)
from app.services.grading_extraction import CustomerDayCandidate
from app.services.grading_pipeline import (
    GradeCustomerDayFailure,
    GradeCustomerDayFailureCode,
    GradeCustomerDayResult,
    GradeCustomerDaySuccess,
)
from app.services.grading_runs import (
    GradingRunCreateParams,
    GradingRunConflictError,
    GradingRunValidationError,
    GradingRunRuntimeSnapshot,
    ensure_grading_run_access,
    SqlAlchemyGradingRunStore,
    build_grading_run_store,
    determine_terminal_run_status,
    to_grading_run_summary,
)


GRADING_BATCH_TIMEZONE = "Asia/Dubai"
GRADING_BATCH_UTC_OFFSET = timedelta(hours=4)


@dataclass(frozen=True, slots=True)
class GradingBatchWindow:
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class GradingBatchPlan:
    window: GradingBatchWindow
    candidates: tuple[CustomerDayCandidate, ...]
    skipped_candidates: tuple[CustomerDayCandidate, ...]
    rerun_existing: bool

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def skipped_candidate_count(self) -> int:
        return len(self.skipped_candidates)


@dataclass(frozen=True, slots=True)
class GradingBatchExecutionRequest:
    window: GradingBatchWindow
    trigger_type: GradingRunTriggerTypeSchema
    run_mode: GradingRunModeSchema
    rerun_existing: bool
    requested_by_account_id: UUID | None = None


class CustomerDayCandidateLoader(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> list[CustomerDayCandidate]: ...


class CustomerDayBatchGrader(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        candidate: CustomerDayCandidate,
    ) -> GradeCustomerDayResult: ...


class GradingBatchExecutor(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        request: GradingBatchExecutionRequest,
    ) -> UUID: ...


def build_manual_batch_execution_request(
    trigger_request: GradingRunTriggerRequest,
    *,
    requested_by_account_id: UUID,
) -> GradingBatchExecutionRequest:
    run_mode = (
        GradingRunModeSchema.RERUN
        if trigger_request.rerun_existing
        else GradingRunModeSchema.BACKFILL
    )
    return GradingBatchExecutionRequest(
        window=GradingBatchWindow(
            start_date=trigger_request.target_start_date,
            end_date=trigger_request.target_end_date,
        ),
        trigger_type=GradingRunTriggerTypeSchema.MANUAL,
        run_mode=run_mode,
        rerun_existing=trigger_request.rerun_existing,
        requested_by_account_id=requested_by_account_id,
    )


def build_run_create_params(
    request: GradingBatchExecutionRequest,
    *,
    runtime_snapshot: GradingRunRuntimeSnapshot,
) -> GradingRunCreateParams:
    return GradingRunCreateParams(
        trigger_type=request.trigger_type,
        run_mode=request.run_mode,
        status=GradingRunStatusSchema.QUEUED,
        target_start_date=request.window.start_date,
        target_end_date=request.window.end_date,
        rerun_existing=request.rerun_existing,
        runtime_snapshot=runtime_snapshot,
        requested_by_account_id=request.requested_by_account_id,
    )


def build_grading_run_runtime_snapshot(
    settings: Settings | None = None,
) -> GradingRunRuntimeSnapshot:
    resolved_settings = settings or get_settings()
    return GradingRunRuntimeSnapshot(
        provider=resolved_settings.grading_provider,
        model=resolved_settings.grading_model,
        prompt_version=resolved_settings.grading_prompt_version,
    )


def get_previous_gst_business_day() -> date:
    now_utc = datetime.now(timezone.utc)
    now_gst = now_utc + GRADING_BATCH_UTC_OFFSET
    today_gst = now_gst.date()
    previous_day = today_gst - timedelta(days=1)
    while previous_day.weekday() >= 5:
        previous_day -= timedelta(days=1)
    return previous_day


def plan_scheduled_batch_window() -> GradingBatchWindow:
    previous_day = get_previous_gst_business_day()
    return GradingBatchWindow(start_date=previous_day, end_date=previous_day)


def plan_manual_batch_window(
    trigger_request: GradingRunTriggerRequest,
    settings: Settings | None = None,
) -> GradingBatchWindow:
    if settings is None:
        settings = get_settings()

    if (
        trigger_request.target_start_date is not None
        and trigger_request.target_end_date is not None
    ):
        start = trigger_request.target_start_date
        end = trigger_request.target_end_date
    elif trigger_request.grade_date is not None:
        start = trigger_request.target_start_date
        end = trigger_request.target_end_date
    else:
        raise ValueError(
            "Either grade_date or target_start_date/target_end_date must be provided."
        )

    if start > end:
        raise ValueError(
            "target_start_date must be less than or equal to target_end_date."
        )

    max_span = settings.grading_batch_max_backfill_days
    span_days = (end - start).days + 1
    if span_days > max_span:
        raise ValueError(
            f"Date window span ({span_days} days) exceeds maximum allowed "
            f"backfill of {max_span} days."
        )

    previous_gst_day = get_previous_gst_business_day()
    if end > previous_gst_day:
        raise ValueError(
            f"target_end_date ({end}) cannot be later than the previous GST "
            f"business day ({previous_gst_day})."
        )

    return GradingBatchWindow(start_date=start, end_date=end)


async def create_queued_grading_run(
    session: AsyncSession,
    request: GradingBatchExecutionRequest,
    *,
    settings: Settings | None = None,
    store: SqlAlchemyGradingRunStore | None = None,
) -> GradingRun:
    resolved_store = store or build_grading_run_store()
    create_params = build_run_create_params(
        request,
        runtime_snapshot=build_grading_run_runtime_snapshot(settings),
    )
    return await resolved_store.create_run(session, create_params)


async def prepare_manual_grading_run(
    session: AsyncSession,
    *,
    current_account: Account,
    trigger_request: GradingRunTriggerRequest,
    settings: Settings | None = None,
    store: SqlAlchemyGradingRunStore | None = None,
):
    from app.schemas.grading_runs import GradingRunTriggerResponse

    ensure_grading_run_access(current_account)

    resolved_settings = settings or get_settings()
    resolved_store = store or build_grading_run_store()

    try:
        window = plan_manual_batch_window(trigger_request, resolved_settings)
    except ValueError as exc:
        raise GradingRunValidationError(
            message="Manual grading run request is invalid.",
            details=(str(exc),),
        ) from exc

    duplicate_active_window = await check_duplicate_active_runs(
        session,
        window.start_date,
        window.end_date,
    )
    if duplicate_active_window:
        raise GradingRunConflictError(
            "A grading run is already active for the requested date window."
        )

    execution_request = build_manual_batch_execution_request(
        trigger_request,
        requested_by_account_id=current_account.id,
    )
    run = await create_queued_grading_run(
        session,
        execution_request,
        settings=resolved_settings,
        store=resolved_store,
    )
    await session.commit()
    await session.refresh(run)
    return (
        GradingRunTriggerResponse(run=to_grading_run_summary(run)),
        execution_request,
    )


async def check_existing_grades(
    session: AsyncSession,
    candidates: list[CustomerDayCandidate],
) -> set[tuple[str, str, date]]:
    if not candidates:
        return set()

    identity_filter_clauses = []
    for candidate in candidates:
        identity_filter_clauses.append(
            (ConversationGrade.identity_type == candidate.identity_type.value)
            & (
                ConversationGrade.conversation_identity
                == candidate.conversation_identity
            )
            & (ConversationGrade.grade_date == candidate.grade_date)
        )

    if not identity_filter_clauses:
        return set()

    from sqlalchemy import or_

    existing_stmt = select(
        ConversationGrade.identity_type,
        ConversationGrade.conversation_identity,
        ConversationGrade.grade_date,
    ).where(or_(*identity_filter_clauses))

    result = await session.execute(existing_stmt)
    rows = result.fetchall()

    return {
        (row.identity_type, row.conversation_identity, row.grade_date) for row in rows
    }


async def plan_batch_candidates(
    session: AsyncSession,
    window: GradingBatchWindow,
    rerun_existing: bool,
) -> GradingBatchPlan:
    from app.services.grading_extraction import list_customer_day_candidates

    candidates = await list_customer_day_candidates(
        session,
        start_date=window.start_date,
        end_date=window.end_date,
    )

    if not candidates:
        return GradingBatchPlan(
            window=window,
            candidates=(),
            skipped_candidates=(),
            rerun_existing=rerun_existing,
        )

    if rerun_existing:
        return GradingBatchPlan(
            window=window,
            candidates=tuple(candidates),
            skipped_candidates=(),
            rerun_existing=True,
        )

    existing_keys = await check_existing_grades(session, candidates)
    skipped_candidates = []
    included_candidates = []

    for candidate in candidates:
        candidate_key = (
            candidate.identity_type.value,
            candidate.conversation_identity,
            candidate.grade_date,
        )
        if candidate_key in existing_keys:
            skipped_candidates.append(candidate)
        else:
            included_candidates.append(candidate)

    return GradingBatchPlan(
        window=window,
        candidates=tuple(included_candidates),
        skipped_candidates=tuple(skipped_candidates),
        rerun_existing=False,
    )


def compute_advisory_lock_key(start_date: date, end_date: date) -> int:
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    combined_str = f"{start_str}:{end_str}"
    hash_value = 0
    for char in combined_str:
        hash_value = ((hash_value << 5) - hash_value) + ord(char)
        hash_value = hash_value & 0xFFFFFFFF
    return hash_value % (2**31)


async def check_duplicate_active_runs(
    session: AsyncSession,
    start_date: date,
    end_date: date,
) -> bool:
    from app.models.grading_runs import GradingRun

    stmt = select(GradingRun).where(
        GradingRun.target_start_date == start_date,
        GradingRun.target_end_date == end_date,
        GradingRun.status.in_(["queued", "running"]),
    )
    result = await session.execute(stmt)
    return result.fetchone() is not None


async def acquire_advisory_lock(
    session: AsyncSession,
    lock_key: int,
) -> bool:
    try:
        result = await session.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
        row = result.fetchone()
        return row[0] if row else False
    except Exception:
        return False


async def release_advisory_lock(
    session: AsyncSession,
    lock_key: int,
) -> None:
    try:
        await session.execute(text(f"SELECT pg_advisory_unlock({lock_key})"))
    except Exception:
        pass


async def persist_failed_run(
    session: AsyncSession,
    run: GradingRun,
    *,
    store: SqlAlchemyGradingRunStore,
    error_message: str,
) -> GradingRun:
    current_status = GradingRunStatusSchema(run.status)
    if current_status in {
        GradingRunStatusSchema.QUEUED,
        GradingRunStatusSchema.RUNNING,
    }:
        await store.update_run_status(
            session,
            run,
            GradingRunStatusSchema.FAILED,
            error_message=error_message,
        )
    await session.commit()
    return run


def build_default_batch_grader(
    settings: Settings | None = None,
) -> CustomerDayBatchGrader:
    from app.services.grading_parser import parse_prompt_execution_results
    from app.services.grading_persistence import upsert_customer_day_grade
    from app.services.grading_pipeline import (
        build_grading_pipeline_dependencies,
        grade_customer_day,
    )
    from app.services.grading_prompt import build_prompt_execution_plan
    from app.services.grading_prompt_assets import load_prompt_pack
    from app.services.grading_provider import build_grading_provider

    resolved_settings = settings or get_settings()
    prompt_pack = load_prompt_pack(settings=resolved_settings)
    dependencies = build_grading_pipeline_dependencies(
        settings=resolved_settings,
        prompt_planner=lambda transcript: build_prompt_execution_plan(
            transcript,
            prompt_pack=prompt_pack,
        ),
        provider=build_grading_provider(settings=resolved_settings),
        parser=parse_prompt_execution_results,
        persistence=upsert_customer_day_grade,
    )

    async def grader(
        session: AsyncSession,
        candidate: CustomerDayCandidate,
    ) -> GradeCustomerDayResult:
        return await grade_customer_day(
            session,
            candidate,
            dependencies,
        )

    return grader


class GradingBatchRunner:
    def __init__(
        self,
        session: AsyncSession,
        grader: CustomerDayBatchGrader,
        run_store: SqlAlchemyGradingRunStore,
    ) -> None:
        self._session = session
        self._grader = grader
        self._run_store = run_store

    async def execute_run(
        self,
        run: GradingRun,
        plan: GradingBatchPlan,
    ) -> GradingRun:
        await self._run_store.update_run_status(
            self._session,
            run,
            GradingRunStatusSchema.RUNNING,
        )

        try:
            for candidate in plan.skipped_candidates:
                await self._record_run_item_skipped(run, candidate)

            for candidate in plan.candidates:
                await self._process_candidate(run, candidate)

            terminal_status = determine_terminal_run_status(run)
            await self._run_store.update_run_status(
                self._session,
                run,
                terminal_status,
            )
        except Exception as exc:
            await self._run_store.update_run_status(
                self._session,
                run,
                GradingRunStatusSchema.FAILED,
                error_message=str(exc)[:500],
            )
            raise

        await self._session.commit()
        return run

    async def _process_candidate(
        self,
        run: GradingRun,
        candidate: CustomerDayCandidate,
    ) -> None:
        result = await self._grader(self._session, candidate)

        if isinstance(result, GradeCustomerDaySuccess):
            await self._record_run_item_success(run, candidate, result)
        elif isinstance(result, GradeCustomerDayFailure):
            await self._record_run_item_failure(run, candidate, result)

    async def _check_candidate_already_graded(
        self,
        candidate_key: tuple[str, str, date],
    ) -> bool:
        identity_type, conversation_identity, grade_date = candidate_key
        stmt = select(ConversationGrade).where(
            ConversationGrade.identity_type == identity_type,
            ConversationGrade.conversation_identity == conversation_identity,
            ConversationGrade.grade_date == grade_date,
        )
        result = await self._session.execute(stmt)
        return result.fetchone() is not None

    async def _record_run_item_success(
        self,
        run: GradingRun,
        candidate: CustomerDayCandidate,
        result: GradeCustomerDaySuccess,
    ) -> None:
        from app.services.grading_runs import GradingRunItemCreateParams

        await self._run_store.create_run_item(
            self._session,
            run,
            GradingRunItemCreateParams(
                identity_type=candidate.identity_type,
                conversation_identity=candidate.conversation_identity,
                grade_date=candidate.grade_date,
                status=GradingRunItemStatusSchema.SUCCESS,
                grade_id=getattr(result.output, "id", None),
            ),
        )

    async def _record_run_item_failure(
        self,
        run: GradingRun,
        candidate: CustomerDayCandidate,
        result: GradeCustomerDayFailure,
    ) -> None:
        from app.services.grading_runs import GradingRunItemCreateParams

        status_map = {
            GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT: GradingRunItemStatusSchema.EMPTY_TRANSCRIPT,
            GradeCustomerDayFailureCode.PROVIDER_ERROR: GradingRunItemStatusSchema.PROVIDER_ERROR,
            GradeCustomerDayFailureCode.PARSE_ERROR: GradingRunItemStatusSchema.PARSE_ERROR,
        }
        status = status_map.get(result.code, GradingRunItemStatusSchema.PROVIDER_ERROR)

        await self._run_store.create_run_item(
            self._session,
            run,
            GradingRunItemCreateParams(
                identity_type=candidate.identity_type,
                conversation_identity=candidate.conversation_identity,
                grade_date=candidate.grade_date,
                status=status,
                error_message=result.message[:500] if result.message else None,
                error_details=result.details,
            ),
        )

    async def _record_run_item_skipped(
        self,
        run: GradingRun,
        candidate: CustomerDayCandidate,
    ) -> None:
        from app.services.grading_runs import GradingRunItemCreateParams

        await self._run_store.create_run_item(
            self._session,
            run,
            GradingRunItemCreateParams(
                identity_type=candidate.identity_type,
                conversation_identity=candidate.conversation_identity,
                grade_date=candidate.grade_date,
                status=GradingRunItemStatusSchema.SKIPPED_EXISTING,
            ),
        )


async def execute_grading_batch(
    session: AsyncSession,
    request: GradingBatchExecutionRequest,
    grader: CustomerDayBatchGrader,
    settings: Settings | None = None,
) -> GradingRun:
    if settings is None:
        settings = get_settings()

    store = build_grading_run_store()

    duplicate_check = await check_duplicate_active_runs(
        session,
        request.window.start_date,
        request.window.end_date,
    )
    if duplicate_check:
        run = await create_queued_grading_run(
            session,
            request,
            settings=settings,
            store=store,
        )
        await store.update_run_status(
            session,
            run,
            GradingRunStatusSchema.FAILED,
            error_message=f"A run is already active for the target window {request.window.start_date} to {request.window.end_date}.",
        )
        await session.commit()
        return run

    run = await create_queued_grading_run(
        session,
        request,
        settings=settings,
        store=store,
    )
    await session.commit()
    return await execute_prepared_grading_run(
        session,
        run,
        request,
        grader,
        store=store,
    )


async def execute_prepared_grading_run(
    session: AsyncSession,
    run: GradingRun,
    request: GradingBatchExecutionRequest,
    grader: CustomerDayBatchGrader,
    *,
    store: SqlAlchemyGradingRunStore | None = None,
) -> GradingRun:
    resolved_store = store or build_grading_run_store()

    if GradingRunStatusSchema(run.status) is not GradingRunStatusSchema.QUEUED:
        raise ValueError("Only queued grading runs can be executed.")

    lock_key = compute_advisory_lock_key(
        request.window.start_date,
        request.window.end_date,
    )
    lock_acquired = await acquire_advisory_lock(session, lock_key)
    if not lock_acquired:
        await resolved_store.update_run_status(
            session,
            run,
            GradingRunStatusSchema.FAILED,
            error_message=f"Could not acquire advisory lock for window {request.window.start_date} to {request.window.end_date}.",
        )
        await session.commit()
        return run

    try:
        plan = await plan_batch_candidates(
            session,
            request.window,
            request.rerun_existing,
        )

        runner = GradingBatchRunner(session, grader, resolved_store)
        return await runner.execute_run(run, plan)
    except Exception as exc:
        return await persist_failed_run(
            session,
            run,
            store=resolved_store,
            error_message=str(exc)[:500],
        )
    finally:
        await release_advisory_lock(session, lock_key)


async def run_grading_batch_in_background(
    run_id: UUID,
    request: GradingBatchExecutionRequest,
    *,
    settings: Settings | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        store = build_grading_run_store()
        run = await store.get_run(session, run_id)
        if run is None:
            return

        try:
            grader = build_default_batch_grader(resolved_settings)
        except Exception as exc:
            await persist_failed_run(
                session,
                run,
                store=store,
                error_message=str(exc)[:500],
            )
            return

        await execute_prepared_grading_run(
            session,
            run,
            request,
            grader,
            store=store,
        )
