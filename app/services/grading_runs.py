from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.enums import AccountRole, IdentityType
from app.models.grading_runs import GradingRun, GradingRunItem
from app.schemas.grading_runs import (
    GradingRunDetailResponse,
    GradingRunItemStatusSchema,
    GradingRunItemSummary,
    GradingRunListQuery,
    GradingRunListResponse,
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunSummary,
    GradingRunTriggerTypeSchema,
)


_RUN_STATUS_TRANSITIONS: dict[
    GradingRunStatusSchema,
    frozenset[GradingRunStatusSchema],
] = {
    GradingRunStatusSchema.QUEUED: frozenset(
        {
            GradingRunStatusSchema.RUNNING,
            GradingRunStatusSchema.FAILED,
        }
    ),
    GradingRunStatusSchema.RUNNING: frozenset(
        {
            GradingRunStatusSchema.COMPLETED,
            GradingRunStatusSchema.COMPLETED_WITH_FAILURES,
            GradingRunStatusSchema.FAILED,
        }
    ),
    GradingRunStatusSchema.COMPLETED: frozenset(),
    GradingRunStatusSchema.COMPLETED_WITH_FAILURES: frozenset(),
    GradingRunStatusSchema.FAILED: frozenset(),
}

_RUN_ITEM_COUNTER_FIELD_BY_STATUS: dict[GradingRunItemStatusSchema, str] = {
    GradingRunItemStatusSchema.SUCCESS: "success_count",
    GradingRunItemStatusSchema.SKIPPED_EXISTING: "skipped_existing_count",
    GradingRunItemStatusSchema.EMPTY_TRANSCRIPT: "empty_transcript_count",
    GradingRunItemStatusSchema.PROVIDER_ERROR: "provider_error_count",
    GradingRunItemStatusSchema.PARSE_ERROR: "parse_error_count",
}
_RUN_ITEM_ATTEMPTED_STATUSES: frozenset[GradingRunItemStatusSchema] = frozenset(
    {
        GradingRunItemStatusSchema.SUCCESS,
        GradingRunItemStatusSchema.EMPTY_TRANSCRIPT,
        GradingRunItemStatusSchema.PROVIDER_ERROR,
        GradingRunItemStatusSchema.PARSE_ERROR,
    }
)
_ERROR_MESSAGE_MAX_LENGTH = 500
_ERROR_DETAIL_MAX_LENGTH = 500
_ERROR_DETAILS_MAX_ITEMS = 10


@dataclass(frozen=True, slots=True)
class GradingRunRuntimeSnapshot:
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class GradingRunCreateParams:
    trigger_type: GradingRunTriggerTypeSchema
    run_mode: GradingRunModeSchema
    status: GradingRunStatusSchema
    target_start_date: date
    target_end_date: date
    rerun_existing: bool
    runtime_snapshot: GradingRunRuntimeSnapshot
    requested_by_account_id: UUID | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class GradingRunItemCreateParams:
    identity_type: IdentityType
    conversation_identity: str
    grade_date: date
    status: GradingRunItemStatusSchema
    grade_id: UUID | None = None
    error_message: str | None = None
    error_details: tuple[str, ...] = ()


@dataclass(slots=True)
class GradingRunStateTransitionError(ValueError):
    current_status: GradingRunStatusSchema
    next_status: GradingRunStatusSchema

    def __str__(self) -> str:
        return (
            "Invalid grading run status transition: "
            f"{self.current_status.value} -> {self.next_status.value}."
        )


@dataclass(slots=True)
class GradingRunItemRecordingError(ValueError):
    run_id: UUID
    status: GradingRunStatusSchema

    def __str__(self) -> str:
        return (
            f"Cannot record run items for run {self.run_id} while status is "
            f"{self.status.value}."
        )


@dataclass(slots=True)
class GradingRunPermissionError(PermissionError):
    account_id: UUID
    role: str | None

    def __str__(self) -> str:
        return "Only super_admin accounts may manage grading runs."


@dataclass(slots=True)
class GradingRunValidationError(ValueError):
    message: str
    details: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class GradingRunConflictError(RuntimeError):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class GradingRunNotFoundError(LookupError):
    run_id: UUID

    def __str__(self) -> str:
        return f"Grading run {self.run_id} was not found."


class GradingRunReader(Protocol):
    async def list_runs(
        self,
        session: AsyncSession,
        filters: GradingRunListQuery,
    ) -> tuple[list[GradingRun], int]: ...

    async def get_run(
        self,
        session: AsyncSession,
        run_id: UUID,
    ) -> GradingRun | None: ...


class GradingRunWriter(Protocol):
    async def create_run(
        self,
        session: AsyncSession,
        params: GradingRunCreateParams,
    ) -> GradingRun: ...

    async def update_run_status(
        self,
        session: AsyncSession,
        run: GradingRun,
        status: GradingRunStatusSchema,
        *,
        error_message: str | None = None,
    ) -> GradingRun: ...

    async def create_run_item(
        self,
        session: AsyncSession,
        run: GradingRun,
        params: GradingRunItemCreateParams,
    ) -> GradingRunItem: ...


class SqlAlchemyGradingRunStore:
    async def list_runs(
        self,
        session: AsyncSession,
        filters: GradingRunListQuery,
    ) -> tuple[list[GradingRun], int]:
        clauses = _build_run_filter_clauses(filters)
        total = await session.scalar(
            select(func.count()).select_from(GradingRun).where(*clauses)
        )
        result = await session.execute(
            select(GradingRun)
            .where(*clauses)
            .order_by(GradingRun.created_at.desc(), GradingRun.id.desc())
            .offset(filters.offset)
            .limit(filters.limit)
        )
        runs = list(result.scalars().all())
        return runs, int(total or 0)

    async def get_run(
        self,
        session: AsyncSession,
        run_id: UUID,
    ) -> GradingRun | None:
        return await session.scalar(
            select(GradingRun).where(GradingRun.id == run_id).limit(1)
        )

    async def create_run(
        self,
        session: AsyncSession,
        params: GradingRunCreateParams,
    ) -> GradingRun:
        if params.status is not GradingRunStatusSchema.QUEUED:
            raise ValueError("Runs must be created in queued status.")

        run = GradingRun(
            trigger_type=params.trigger_type.value,
            run_mode=params.run_mode.value,
            status=params.status.value,
            target_start_date=params.target_start_date,
            target_end_date=params.target_end_date,
            rerun_existing=params.rerun_existing,
            provider=_normalize_bounded_string(
                params.runtime_snapshot.provider,
                field_name="provider",
                max_length=64,
            ),
            model=_normalize_bounded_string(
                params.runtime_snapshot.model,
                field_name="model",
                max_length=128,
            ),
            prompt_version=_normalize_bounded_string(
                params.runtime_snapshot.prompt_version,
                field_name="prompt_version",
                max_length=64,
            ),
            candidate_count=0,
            attempted_count=0,
            success_count=0,
            skipped_existing_count=0,
            empty_transcript_count=0,
            provider_error_count=0,
            parse_error_count=0,
            requested_by_account_id=params.requested_by_account_id,
            error_message=_normalize_optional_bounded_string(
                params.error_message,
                field_name="error_message",
                max_length=_ERROR_MESSAGE_MAX_LENGTH,
            ),
        )
        session.add(run)
        await session.flush()
        return run

    async def update_run_status(
        self,
        session: AsyncSession,
        run: GradingRun,
        status: GradingRunStatusSchema,
        *,
        error_message: str | None = None,
    ) -> GradingRun:
        current_status = GradingRunStatusSchema(run.status)
        next_status = GradingRunStatusSchema(status)
        if next_status not in _RUN_STATUS_TRANSITIONS[current_status]:
            raise GradingRunStateTransitionError(
                current_status=current_status,
                next_status=next_status,
            )

        normalized_error_message = _normalize_optional_bounded_string(
            error_message,
            field_name="error_message",
            max_length=_ERROR_MESSAGE_MAX_LENGTH,
        )
        if next_status is not GradingRunStatusSchema.FAILED and normalized_error_message:
            raise ValueError("error_message is only allowed for failed runs.")

        now = _utcnow()
        run.status = next_status.value
        if next_status is GradingRunStatusSchema.RUNNING:
            run.started_at = run.started_at or now
            run.finished_at = None
            run.error_message = None
        else:
            if next_status is GradingRunStatusSchema.FAILED:
                run.error_message = normalized_error_message
            else:
                run.error_message = None
            if current_status is GradingRunStatusSchema.RUNNING and run.started_at is None:
                run.started_at = now
            run.finished_at = now

        await session.flush()
        return run

    async def create_run_item(
        self,
        session: AsyncSession,
        run: GradingRun,
        params: GradingRunItemCreateParams,
    ) -> GradingRunItem:
        run_status = GradingRunStatusSchema(run.status)
        if run_status is not GradingRunStatusSchema.RUNNING:
            raise GradingRunItemRecordingError(run_id=run.id, status=run_status)

        now = _utcnow()
        item_status = GradingRunItemStatusSchema(params.status)
        item = GradingRunItem(
            run_id=run.id,
            identity_type=params.identity_type.value,
            conversation_identity=_normalize_bounded_string(
                params.conversation_identity,
                field_name="conversation_identity",
                max_length=255,
            ),
            grade_date=params.grade_date,
            status=item_status.value,
            grade_id=params.grade_id,
            error_message=_normalize_optional_bounded_string(
                params.error_message,
                field_name="error_message",
                max_length=_ERROR_MESSAGE_MAX_LENGTH,
            ),
            error_details=_normalize_error_details(params.error_details),
            started_at=now,
            finished_at=now,
        )
        session.add(item)
        _apply_run_item_counters(run, item_status)
        await session.flush()
        return item


def build_grading_run_store() -> SqlAlchemyGradingRunStore:
    return SqlAlchemyGradingRunStore()


def ensure_grading_run_access(account: Account) -> None:
    if account.role_enum is not AccountRole.SUPER_ADMIN:
        raise GradingRunPermissionError(
            account_id=account.id,
            role=account.role,
        )


async def list_grading_run_history(
    session: AsyncSession,
    *,
    current_account: Account,
    filters: GradingRunListQuery,
    store: GradingRunReader | None = None,
) -> GradingRunListResponse:
    ensure_grading_run_access(current_account)

    resolved_store = store or build_grading_run_store()
    runs, total = await resolved_store.list_runs(session, filters)
    return GradingRunListResponse(
        items=[to_grading_run_summary(run) for run in runs],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


async def get_grading_run_history_detail(
    session: AsyncSession,
    *,
    current_account: Account,
    run_id: UUID,
    store: GradingRunReader | None = None,
) -> GradingRunDetailResponse:
    ensure_grading_run_access(current_account)

    resolved_store = store or build_grading_run_store()
    run = await resolved_store.get_run(session, run_id)
    if run is None:
        raise GradingRunNotFoundError(run_id=run_id)

    items_result = await session.execute(
        select(GradingRunItem)
        .where(GradingRunItem.run_id == run_id)
        .order_by(
            GradingRunItem.grade_date.asc(),
            GradingRunItem.conversation_identity.asc(),
            GradingRunItem.id.asc(),
        )
    )
    items = list(items_result.scalars().all())

    return GradingRunDetailResponse(
        run=to_grading_run_summary(run),
        items=[to_grading_run_item_summary(item) for item in items],
    )


def to_grading_run_summary(run: GradingRun) -> GradingRunSummary:
    return GradingRunSummary(
        id=run.id,
        trigger_type=run.trigger_type,
        run_mode=run.run_mode,
        status=run.status,
        target_start_date=run.target_start_date,
        target_end_date=run.target_end_date,
        rerun_existing=run.rerun_existing,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        candidate_count=run.candidate_count,
        attempted_count=run.attempted_count,
        success_count=run.success_count,
        skipped_existing_count=run.skipped_existing_count,
        empty_transcript_count=run.empty_transcript_count,
        provider_error_count=run.provider_error_count,
        parse_error_count=run.parse_error_count,
        requested_by_account_id=run.requested_by_account_id,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def to_grading_run_item_summary(item: GradingRunItem) -> GradingRunItemSummary:
    return GradingRunItemSummary(
        identity_type=item.identity_type,
        conversation_identity=item.conversation_identity,
        grade_date=item.grade_date,
        status=item.status,
        grade_id=item.grade_id,
        error_message=item.error_message,
        error_details=list(item.error_details or []),
        started_at=item.started_at,
        finished_at=item.finished_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def determine_terminal_run_status(run: GradingRun) -> GradingRunStatusSchema:
    if (
        run.empty_transcript_count > 0
        or run.provider_error_count > 0
        or run.parse_error_count > 0
    ):
        return GradingRunStatusSchema.COMPLETED_WITH_FAILURES
    return GradingRunStatusSchema.COMPLETED


def _build_run_filter_clauses(filters: GradingRunListQuery) -> tuple[object, ...]:
    clauses: list[object] = []
    if filters.status is not None:
        clauses.append(GradingRun.status == filters.status.value)
    if filters.trigger_type is not None:
        clauses.append(GradingRun.trigger_type == filters.trigger_type.value)
    if filters.run_mode is not None:
        clauses.append(GradingRun.run_mode == filters.run_mode.value)
    if filters.target_start_date is not None:
        clauses.append(GradingRun.target_start_date >= filters.target_start_date)
    if filters.target_end_date is not None:
        clauses.append(GradingRun.target_end_date <= filters.target_end_date)
    return tuple(clauses)


def _apply_run_item_counters(
    run: GradingRun,
    item_status: GradingRunItemStatusSchema,
) -> None:
    run.candidate_count += 1
    if item_status in _RUN_ITEM_ATTEMPTED_STATUSES:
        run.attempted_count += 1

    counter_field = _RUN_ITEM_COUNTER_FIELD_BY_STATUS[item_status]
    setattr(run, counter_field, getattr(run, counter_field) + 1)


def _normalize_error_details(values: tuple[str, ...]) -> list[str] | None:
    normalized_values: list[str] = []
    for raw_value in values:
        normalized = _normalize_bounded_string(
            raw_value,
            field_name="error_details",
            max_length=_ERROR_DETAIL_MAX_LENGTH,
        )
        normalized_values.append(normalized)
        if len(normalized_values) >= _ERROR_DETAILS_MAX_ITEMS:
            break
    return normalized_values or None


def _normalize_bounded_string(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized[:max_length]


def _normalize_optional_bounded_string(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    return _normalize_bounded_string(
        value,
        field_name=field_name,
        max_length=max_length,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
