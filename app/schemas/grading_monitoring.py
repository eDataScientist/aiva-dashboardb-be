from __future__ import annotations

from datetime import date as calendar_date
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from app.core import (
    GRADING_BATCH_TIMEZONE,
    GRADING_ESCALATION_TYPE_VALUES,
    HIGHLIGHT_CODE_TO_LABEL,
    INTENT_CODE_TO_CATEGORY,
    INTENT_CODE_TO_LABEL,
    MONITORING_ALLOWED_SORT_DIRECTIONS,
    MONITORING_ALLOWED_SORT_FIELDS,
    get_settings,
)
from app.schemas.analytics import SchemaModel
from app.schemas.grading_metrics import GradingMetricsDateWindow, GradingMetricsFreshness

_GST_ZONE = ZoneInfo(GRADING_BATCH_TIMEZONE)


def _previous_gst_day() -> calendar_date:
    return datetime.now(tz=_GST_ZONE).date() - timedelta(days=1)


class MonitoringErrorCode(str, Enum):
    INVALID_DATE_WINDOW = "invalid_date_window"
    INVALID_INTENT_FILTER = "invalid_intent_filter"
    INVALID_ESCALATION_FILTER = "invalid_escalation_filter"
    INVALID_SORT = "invalid_sort"
    GRADE_NOT_FOUND = "grade_not_found"


class MonitoringHighlightBadge(SchemaModel):
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in HIGHLIGHT_CODE_TO_LABEL:
            raise ValueError("code must be a supported monitoring highlight code.")
        return normalized

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("label must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_alignment(self) -> "MonitoringHighlightBadge":
        if self.label != HIGHLIGHT_CODE_TO_LABEL[self.code]:
            raise ValueError("label must match the canonical highlight label.")
        return self


class MonitoringErrorResponse(SchemaModel):
    code: MonitoringErrorCode
    message: str = Field(min_length=1)
    details: list[str] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank.")
        return normalized

    @field_validator("details")
    @classmethod
    def validate_details(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized:
                raise ValueError("details must not contain blank items.")
            normalized_values.append(normalized)
        return normalized_values


class MonitoringConversationListQuery(SchemaModel):
    start_date: calendar_date | None = Field(default=None)
    end_date: calendar_date | None = Field(default=None)
    resolution: bool | None = Field(default=None)
    escalation_types: list[str] = Field(default_factory=list)
    frustration_min: int | None = Field(default=None, ge=1, le=10)
    accuracy_max: int | None = Field(default=None, ge=1, le=10)
    intent_codes: list[str] = Field(default_factory=list)
    sort_by: str | None = Field(default=None)
    sort_direction: str = Field(default="desc")
    limit: int | None = Field(default=None)
    offset: int = Field(default=0, ge=0)

    @field_validator("intent_codes")
    @classmethod
    def normalize_intent_codes(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip().lower()
            if not normalized:
                raise ValueError("intent_codes must not contain blank items.")
            if normalized not in INTENT_CODE_TO_LABEL:
                raise ValueError(f"Unsupported canonical intent code: {value!r}.")
            if normalized not in seen:
                seen.add(normalized)
                normalized_values.append(normalized)
        return normalized_values

    @field_validator("escalation_types")
    @classmethod
    def normalize_escalation_types(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        seen: set[str] = set()
        allowed = {value.lower(): value for value in GRADING_ESCALATION_TYPE_VALUES}
        for value in values:
            normalized = value.strip()
            if not normalized:
                raise ValueError("escalation_types must not contain blank items.")
            canonical = allowed.get(normalized.lower())
            if canonical is None:
                raise ValueError(f"Unsupported escalation type: {value!r}.")
            if canonical not in seen:
                seen.add(canonical)
                normalized_values.append(canonical)
        return normalized_values

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized not in MONITORING_ALLOWED_SORT_FIELDS:
            raise ValueError(
                "sort_by must be one of: " + ", ".join(MONITORING_ALLOWED_SORT_FIELDS)
            )
        return normalized

    @field_validator("sort_direction")
    @classmethod
    def validate_sort_direction(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in MONITORING_ALLOWED_SORT_DIRECTIONS:
            raise ValueError(
                "sort_direction must be one of: "
                + ", ".join(MONITORING_ALLOWED_SORT_DIRECTIONS)
            )
        return normalized

    @model_validator(mode="after")
    def resolve_defaults_and_validate(self) -> "MonitoringConversationListQuery":
        settings = get_settings()
        previous_day = _previous_gst_day()

        resolved_end = self.end_date or previous_day
        resolved_start = self.start_date or (
            resolved_end - timedelta(days=settings.monitoring_default_window_days - 1)
        )
        resolved_limit = self.limit or settings.monitoring_default_page_size

        if resolved_start > resolved_end:
            raise ValueError("start_date must be less than or equal to end_date.")
        if resolved_end > previous_day:
            raise ValueError("end_date must be on or before the previous GST day.")
        if (resolved_end - resolved_start).days + 1 > settings.monitoring_max_window_days:
            raise ValueError(
                "date window must not exceed the configured maximum monitoring range."
            )
        if resolved_limit > settings.monitoring_max_page_size:
            raise ValueError(
                "limit must not exceed the configured maximum monitoring page size."
            )

        self.start_date = resolved_start
        self.end_date = resolved_end
        self.limit = resolved_limit
        return self

    @property
    def date_window(self) -> GradingMetricsDateWindow:
        return GradingMetricsDateWindow(
            start_date=self.start_date,  # type: ignore[arg-type]
            end_date=self.end_date,  # type: ignore[arg-type]
        )


class MonitoringConversationTranscriptMessage(SchemaModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime

    @field_validator("role", "content")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized


class MonitoringConversationHistoryItem(SchemaModel):
    grade_id: UUID
    grade_date: calendar_date
    conversation_key: str = Field(min_length=1)
    resolution: bool | None = Field(default=None)
    escalation_type: str | None = Field(default=None)
    frustration_score: int | None = Field(default=None, ge=1, le=10)
    accuracy_score: int | None = Field(default=None, ge=1, le=10)
    highlights: list[MonitoringHighlightBadge] = Field(default_factory=list)

    @field_validator("conversation_key")
    @classmethod
    def validate_conversation_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("conversation_key must not be blank.")
        return normalized


class MonitoringConversationSummary(SchemaModel):
    grade_id: UUID
    grade_date: calendar_date
    conversation_key: str = Field(min_length=1)
    contact_name: str | None = Field(default=None)
    latest_message_preview: str | None = Field(default=None)
    latest_message_at: datetime | None = Field(default=None)
    message_count: int = Field(ge=0)
    intent_code: str | None = Field(default=None)
    intent_label: str | None = Field(default=None)
    intent_category: str | None = Field(default=None)
    resolution: bool | None = Field(default=None)
    escalation_type: str | None = Field(default=None)
    frustration_score: int | None = Field(default=None, ge=1, le=10)
    accuracy_score: int | None = Field(default=None, ge=1, le=10)
    highlights: list[MonitoringHighlightBadge] = Field(default_factory=list)

    @field_validator(
        "conversation_key",
        "contact_name",
        "latest_message_preview",
        "intent_code",
        "intent_label",
        "intent_category",
    )
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank when provided.")
        return normalized

    @model_validator(mode="after")
    def validate_intent_metadata_alignment(self) -> "MonitoringConversationSummary":
        if self.intent_code is None:
            if self.intent_label is not None or self.intent_category is not None:
                raise ValueError(
                    "intent_label and intent_category require intent_code."
                )
            return self

        normalized_code = self.intent_code.lower()
        if normalized_code not in INTENT_CODE_TO_LABEL:
            raise ValueError("intent_code must be a supported canonical intent code.")
        self.intent_code = normalized_code

        if self.intent_label != INTENT_CODE_TO_LABEL[normalized_code]:
            raise ValueError("intent_label must match the canonical label.")
        if self.intent_category != INTENT_CODE_TO_CATEGORY[normalized_code]:
            raise ValueError("intent_category must match the canonical category.")
        return self


class MonitoringGradePanel(SchemaModel):
    ai_performance: dict[str, object] = Field(default_factory=dict)
    conversation_health: dict[str, object] = Field(default_factory=dict)
    user_signals: dict[str, object] = Field(default_factory=dict)
    escalation: dict[str, object] = Field(default_factory=dict)
    intent: dict[str, object] = Field(default_factory=dict)


class MonitoringConversationDetail(MonitoringConversationSummary):
    message_count: int = Field(default=0, ge=0)
    grade_panel: MonitoringGradePanel
    transcript: list[MonitoringConversationTranscriptMessage] = Field(default_factory=list)
    recent_history: list[MonitoringConversationHistoryItem] = Field(default_factory=list)


class MonitoringConversationListResponse(SchemaModel):
    date_window: GradingMetricsDateWindow
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[MonitoringConversationSummary] = Field(default_factory=list)
    freshness: GradingMetricsFreshness


class MonitoringConversationDetailResponse(SchemaModel):
    detail: MonitoringConversationDetail
