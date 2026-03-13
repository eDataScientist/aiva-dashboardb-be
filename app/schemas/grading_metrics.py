from __future__ import annotations

from datetime import date as calendar_date
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from app.core import (
    GRADING_BATCH_TIMEZONE,
    INTENT_CODE_TO_CATEGORY,
    INTENT_CODE_TO_LABEL,
    get_settings,
)
from app.schemas.analytics import SchemaModel

_GST_ZONE = ZoneInfo(GRADING_BATCH_TIMEZONE)


def _previous_gst_day() -> calendar_date:
    return datetime.now(tz=_GST_ZONE).date() - timedelta(days=1)


class GradingMetricsErrorCode(str, Enum):
    INVALID_DATE_WINDOW = "invalid_date_window"
    INVALID_INTENT_FILTER = "invalid_intent_filter"


class GradingEscalationTypeSchema(str, Enum):
    NATURAL = "Natural"
    FAILURE = "Failure"
    NONE = "None"


class GradingMetricsErrorResponse(SchemaModel):
    code: GradingMetricsErrorCode = Field(
        description="Stable graded-metrics API error code.",
    )
    message: str = Field(min_length=1, description="Human-readable error summary.")
    details: list[str] = Field(
        default_factory=list,
        description="Optional validation details for the rejected metrics request.",
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


class GradingMetricsDateWindow(SchemaModel):
    start_date: calendar_date = Field(
        description="Inclusive GST start date for the metrics window."
    )
    end_date: calendar_date = Field(
        description="Inclusive GST end date for the metrics window."
    )

    @model_validator(mode="after")
    def validate_date_order(self) -> "GradingMetricsDateWindow":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date.")
        return self


class GradingMetricsWindowQuery(SchemaModel):
    start_date: calendar_date | None = Field(
        default=None,
        description="Optional inclusive GST start date. Defaults from the configured metrics window.",
    )
    end_date: calendar_date | None = Field(
        default=None,
        description="Optional inclusive GST end date. Defaults to the previous GST day.",
    )

    @model_validator(mode="after")
    def resolve_and_validate_window(self) -> "GradingMetricsWindowQuery":
        settings = get_settings()
        previous_day = _previous_gst_day()

        resolved_end = self.end_date or previous_day
        resolved_start = self.start_date or (
            resolved_end - timedelta(days=settings.grading_metrics_default_window_days - 1)
        )

        if resolved_start > resolved_end:
            raise ValueError("start_date must be less than or equal to end_date.")
        if resolved_end > previous_day:
            raise ValueError("end_date must be on or before the previous GST day.")

        window_days = (resolved_end - resolved_start).days + 1
        if window_days > settings.grading_metrics_max_window_days:
            raise ValueError(
                "date window must not exceed the configured maximum metrics range."
            )

        self.start_date = resolved_start
        self.end_date = resolved_end
        return self

    @property
    def date_window(self) -> GradingMetricsDateWindow:
        return GradingMetricsDateWindow(
            start_date=self.start_date,  # type: ignore[arg-type]
            end_date=self.end_date,  # type: ignore[arg-type]
        )


class GradingMetricsIntentTrendQuery(GradingMetricsWindowQuery):
    intent_codes: list[str] = Field(
        default_factory=list,
        description=(
            "Optional canonical intent-code filter. Empty means all canonical intent "
            "codes."
        ),
    )

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
                raise ValueError(
                    f"Unsupported canonical intent code: {value!r}."
                )
            if normalized not in seen:
                seen.add(normalized)
                normalized_values.append(normalized)
        return normalized_values


class GradingMetricsFreshness(SchemaModel):
    latest_successful_run_id: UUID | None = Field(
        default=None,
        description="Latest successful grading run identifier, when available.",
    )
    latest_successful_window_end_date: calendar_date | None = Field(
        default=None,
        description="Latest successful GST target end date, when available.",
    )
    latest_successful_run_finished_at: datetime | None = Field(
        default=None,
        description="Completion timestamp for the latest successful run, when available.",
    )


class GradingMetricsAverageScores(SchemaModel):
    relevancy: float = Field(ge=0.0, le=10.0)
    accuracy: float = Field(ge=0.0, le=10.0)
    completeness: float = Field(ge=0.0, le=10.0)
    clarity: float = Field(ge=0.0, le=10.0)
    tone: float = Field(ge=0.0, le=10.0)
    repetition: float = Field(ge=0.0, le=10.0)
    satisfaction: float = Field(ge=0.0, le=10.0)
    frustration: float = Field(ge=0.0, le=10.0)


class GradingMetricsOutcomeRates(SchemaModel):
    resolution_rate_pct: float = Field(ge=0.0, le=100.0)
    loop_detected_rate_pct: float = Field(ge=0.0, le=100.0)
    non_genuine_rate_pct: float = Field(ge=0.0, le=100.0)
    escalation_rate_pct: float = Field(ge=0.0, le=100.0)
    escalation_failure_rate_pct: float = Field(ge=0.0, le=100.0)


class GradingMetricsEscalationBreakdownItem(SchemaModel):
    escalation_type: GradingEscalationTypeSchema = Field(
        description="Canonical escalation type bucket for the selected metrics window.",
    )
    count: int = Field(ge=0, description="Number of graded customer-days in this bucket.")
    share_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage share of the selected window represented by this bucket.",
    )


class GradingMetricsSummaryResponse(SchemaModel):
    date_window: GradingMetricsDateWindow = Field(
        description="Resolved GST metrics date window used for the response.",
    )
    total_graded_customer_days: int = Field(
        ge=0,
        description="Total canonical graded customer-day rows in the selected window.",
    )
    average_scores: GradingMetricsAverageScores = Field(
        description="Selected-window averages for the numeric score metrics.",
    )
    outcome_rates: GradingMetricsOutcomeRates = Field(
        description="Selected-window percentages for key outcome metrics.",
    )
    escalation_breakdown: list[GradingMetricsEscalationBreakdownItem] = Field(
        default_factory=list,
        description="Escalation-type counts and shares for the selected window.",
    )
    freshness: GradingMetricsFreshness = Field(
        description="Latest successful grading freshness metadata.",
    )


class GradingScoreTrendPoint(SchemaModel):
    date: calendar_date = Field(description="GST calendar date bucket.")
    relevancy: float = Field(ge=0.0, le=10.0)
    accuracy: float = Field(ge=0.0, le=10.0)
    completeness: float = Field(ge=0.0, le=10.0)
    clarity: float = Field(ge=0.0, le=10.0)
    tone: float = Field(ge=0.0, le=10.0)
    repetition: float = Field(ge=0.0, le=10.0)
    satisfaction: float = Field(ge=0.0, le=10.0)
    frustration: float = Field(ge=0.0, le=10.0)


class GradingScoreTrendResponse(SchemaModel):
    date_window: GradingMetricsDateWindow = Field(
        description="Resolved GST metrics date window used for the response.",
    )
    points: list[GradingScoreTrendPoint] = Field(
        default_factory=list,
        description="Daily zero-filled average score points sorted by date ascending.",
    )


class GradingOutcomeTrendPoint(SchemaModel):
    date: calendar_date = Field(description="GST calendar date bucket.")
    resolution_rate_pct: float = Field(ge=0.0, le=100.0)
    loop_detected_rate_pct: float = Field(ge=0.0, le=100.0)
    non_genuine_rate_pct: float = Field(ge=0.0, le=100.0)
    escalation_rate_pct: float = Field(ge=0.0, le=100.0)
    escalation_failure_rate_pct: float = Field(ge=0.0, le=100.0)


class GradingOutcomeTrendResponse(SchemaModel):
    date_window: GradingMetricsDateWindow = Field(
        description="Resolved GST metrics date window used for the response.",
    )
    points: list[GradingOutcomeTrendPoint] = Field(
        default_factory=list,
        description="Daily zero-filled outcome-rate points sorted by date ascending.",
    )


class GradingIntentDistributionItem(SchemaModel):
    intent_code: str = Field(
        min_length=1,
        description="Canonical intent code for the selected bucket.",
    )
    intent_label: str = Field(
        min_length=1,
        description="Canonical display label for the selected intent code.",
    )
    intent_category: str = Field(
        min_length=1,
        description="Canonical taxonomy category for the selected intent code.",
    )
    count: int = Field(ge=0, description="Count of graded customer-days in this bucket.")
    share_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage share of the selected window represented by this bucket.",
    )

    @field_validator("intent_code")
    @classmethod
    def validate_intent_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in INTENT_CODE_TO_LABEL:
            raise ValueError("intent_code must be a supported canonical intent code.")
        return normalized

    @field_validator("intent_label", "intent_category")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_intent_metadata_alignment(self) -> "GradingIntentDistributionItem":
        if self.intent_label != INTENT_CODE_TO_LABEL[self.intent_code]:
            raise ValueError("intent_label must match the canonical label.")
        if self.intent_category != INTENT_CODE_TO_CATEGORY[self.intent_code]:
            raise ValueError("intent_category must match the canonical category.")
        return self


class GradingIntentDistributionResponse(SchemaModel):
    date_window: GradingMetricsDateWindow = Field(
        description="Resolved GST metrics date window used for the response.",
    )
    total_graded_customer_days: int = Field(
        ge=0,
        description="Total canonical graded customer-day rows in the selected window.",
    )
    items: list[GradingIntentDistributionItem] = Field(
        default_factory=list,
        description="Canonical intent distribution rows for the selected window.",
    )


class GradingIntentTrendPoint(SchemaModel):
    date: calendar_date = Field(description="GST calendar date bucket.")
    count: int = Field(
        ge=0,
        description="Zero-filled daily count for the selected canonical intent code.",
    )


class GradingIntentTrendSeries(SchemaModel):
    intent_code: str = Field(
        min_length=1,
        description="Canonical intent code represented by this daily series.",
    )
    intent_label: str = Field(
        min_length=1,
        description="Canonical display label for the selected intent code.",
    )
    intent_category: str = Field(
        min_length=1,
        description="Canonical taxonomy category for the selected intent code.",
    )
    points: list[GradingIntentTrendPoint] = Field(
        default_factory=list,
        description="Daily zero-filled count points sorted by date ascending.",
    )

    @field_validator("intent_code")
    @classmethod
    def validate_intent_series_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in INTENT_CODE_TO_LABEL:
            raise ValueError("intent_code must be a supported canonical intent code.")
        return normalized

    @field_validator("intent_label", "intent_category")
    @classmethod
    def validate_series_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_intent_series_alignment(self) -> "GradingIntentTrendSeries":
        if self.intent_label != INTENT_CODE_TO_LABEL[self.intent_code]:
            raise ValueError("intent_label must match the canonical label.")
        if self.intent_category != INTENT_CODE_TO_CATEGORY[self.intent_code]:
            raise ValueError("intent_category must match the canonical category.")
        return self


class GradingIntentTrendResponse(SchemaModel):
    date_window: GradingMetricsDateWindow = Field(
        description="Resolved GST metrics date window used for the response.",
    )
    series: list[GradingIntentTrendSeries] = Field(
        default_factory=list,
        description="Canonical intent trend series for all or selected intent codes.",
    )
