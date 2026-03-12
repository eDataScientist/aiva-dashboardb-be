from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.enums import IdentityType
from app.schemas.analytics import SchemaModel


class GradingRunTriggerTypeSchema(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class GradingRunModeSchema(str, Enum):
    DAILY = "daily"
    BACKFILL = "backfill"
    RERUN = "rerun"


class GradingRunStatusSchema(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"


class GradingRunItemStatusSchema(str, Enum):
    SUCCESS = "success"
    SKIPPED_EXISTING = "skipped_existing"
    EMPTY_TRANSCRIPT = "empty_transcript"
    PROVIDER_ERROR = "provider_error"
    PARSE_ERROR = "parse_error"


class GradingRunErrorCode(str, Enum):
    INVALID_DATE_WINDOW = "invalid_date_window"
    DUPLICATE_ACTIVE_WINDOW = "duplicate_active_window"
    EXECUTION_NOT_ALLOWED = "execution_not_allowed"
    RUN_NOT_FOUND = "run_not_found"


class GradingRunErrorResponse(SchemaModel):
    code: GradingRunErrorCode = Field(description="Stable grading-run API error code.")
    message: str = Field(min_length=1, description="Human-readable error summary.")
    details: list[str] = Field(
        default_factory=list,
        description="Optional validation or operational details.",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank.")
        return normalized

    @field_validator("details")
    @classmethod
    def normalize_details(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized:
                raise ValueError("details must not contain blank items.")
            normalized_values.append(normalized)
        return normalized_values


class GradingRunTriggerRequest(SchemaModel):
    grade_date: date | None = Field(
        default=None,
        description="Single GST date to process as a one-day manual run.",
    )
    start_date: date | None = Field(
        default=None,
        description="Inclusive GST start date for a bounded manual range run.",
    )
    end_date: date | None = Field(
        default=None,
        description="Inclusive GST end date for a bounded manual range run.",
    )
    rerun_existing: bool = Field(
        default=False,
        description="Reprocess customer-days that already have canonical grade rows.",
    )

    @model_validator(mode="after")
    def validate_date_shape(self) -> "GradingRunTriggerRequest":
        has_grade_date = self.grade_date is not None
        has_start_date = self.start_date is not None
        has_end_date = self.end_date is not None

        if has_grade_date and (has_start_date or has_end_date):
            raise ValueError(
                "grade_date cannot be combined with start_date or end_date."
            )
        if not has_grade_date and not has_start_date and not has_end_date:
            raise ValueError(
                "Provide either grade_date or both start_date and end_date."
            )
        if has_start_date != has_end_date:
            raise ValueError("start_date and end_date must be provided together.")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date.")
        return self

    @property
    def target_start_date(self) -> date:
        return self.grade_date or self.start_date  # type: ignore[return-value]

    @property
    def target_end_date(self) -> date:
        return self.grade_date or self.end_date  # type: ignore[return-value]


class GradingRunListQuery(SchemaModel):
    status: GradingRunStatusSchema | None = Field(
        default=None,
        description="Optional run-status filter.",
    )
    trigger_type: GradingRunTriggerTypeSchema | None = Field(
        default=None,
        description="Optional trigger-type filter.",
    )
    run_mode: GradingRunModeSchema | None = Field(
        default=None,
        description="Optional run-mode filter.",
    )
    target_start_date: date | None = Field(
        default=None,
        description="Optional inclusive lower bound for target_start_date filtering.",
    )
    target_end_date: date | None = Field(
        default=None,
        description="Optional inclusive upper bound for target_end_date filtering.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of runs to return.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset for run-history pagination.",
    )

    @model_validator(mode="after")
    def validate_target_range(self) -> "GradingRunListQuery":
        if (
            self.target_start_date is not None
            and self.target_end_date is not None
            and self.target_start_date > self.target_end_date
        ):
            raise ValueError(
                "target_start_date must be less than or equal to target_end_date."
            )
        return self


class GradingRunPathParams(SchemaModel):
    run_id: UUID = Field(description="Opaque grading run identifier.")


class GradingRunItemSummary(SchemaModel):
    identity_type: IdentityType = Field(
        description="Canonical identity type for the customer-day candidate.",
    )
    conversation_identity: str = Field(
        min_length=1,
        description="Canonical identity value for the customer-day candidate.",
    )
    grade_date: date = Field(description="GST grade date for the customer-day candidate.")
    status: GradingRunItemStatusSchema = Field(
        description="Stable candidate outcome recorded for this run item.",
    )
    grade_id: UUID | None = Field(
        default=None,
        description="Canonical grade row written for successful items, when available.",
    )
    error_message: str | None = Field(
        default=None,
        description="Bounded operational error summary for failed items.",
    )
    error_details: list[str] = Field(
        default_factory=list,
        description="Optional bounded detail list for failed items.",
    )
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)

    @field_validator("conversation_identity", "error_message")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank when provided.")
        return normalized

    @field_validator("error_details")
    @classmethod
    def normalize_error_details(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized:
                raise ValueError("error_details must not contain blank items.")
            normalized_values.append(normalized)
        return normalized_values


class GradingRunSummary(SchemaModel):
    id: UUID = Field(description="Grading run identifier.")
    trigger_type: GradingRunTriggerTypeSchema = Field(
        description="How this run was started."
    )
    run_mode: GradingRunModeSchema = Field(
        description="Window semantics for this run."
    )
    status: GradingRunStatusSchema = Field(
        description="Current lifecycle status for the run."
    )
    target_start_date: date = Field(description="Inclusive GST start date for the run.")
    target_end_date: date = Field(description="Inclusive GST end date for the run.")
    rerun_existing: bool = Field(
        description="Whether existing canonical grades were eligible for reprocessing."
    )
    provider: str = Field(min_length=1, description="Provider snapshot used for the run.")
    model: str = Field(min_length=1, description="Model snapshot used for the run.")
    prompt_version: str = Field(
        min_length=1,
        description="Prompt-pack version snapshot used for the run.",
    )
    candidate_count: int = Field(ge=0)
    attempted_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    skipped_existing_count: int = Field(ge=0)
    empty_transcript_count: int = Field(ge=0)
    provider_error_count: int = Field(ge=0)
    parse_error_count: int = Field(ge=0)
    requested_by_account_id: UUID | None = Field(
        default=None,
        description="Account that requested the run, or null for scheduled runs.",
    )
    error_message: str | None = Field(
        default=None,
        description="Bounded run-level abort summary for failed runs.",
    )
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    created_at: datetime = Field(description="Run creation timestamp.")
    updated_at: datetime = Field(description="Run last-update timestamp.")

    @field_validator("provider", "model", "prompt_version", "error_message")
    @classmethod
    def normalize_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank when provided.")
        return normalized


class GradingRunTriggerResponse(SchemaModel):
    run: GradingRunSummary = Field(
        description="Queued or running run summary returned after manual trigger acceptance."
    )


class GradingRunListResponse(SchemaModel):
    items: list[GradingRunSummary] = Field(
        default_factory=list,
        description="Paginated run-history summaries.",
    )
    total: int = Field(ge=0, description="Total runs matching the applied filters.")
    limit: int = Field(ge=1, description="Echoed page size.")
    offset: int = Field(ge=0, description="Echoed page offset.")


class GradingRunDetailResponse(SchemaModel):
    run: GradingRunSummary = Field(description="Detailed run summary.")
    items: list[GradingRunItemSummary] = Field(
        default_factory=list,
        description="Run-item summaries associated with the requested run.",
    )
