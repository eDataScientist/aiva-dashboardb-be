from __future__ import annotations

from datetime import date as calendar_date
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from app.core import GRADING_BATCH_TIMEZONE, get_settings
from app.schemas.analytics import SchemaModel

_GST_ZONE = ZoneInfo(GRADING_BATCH_TIMEZONE)


def _previous_gst_day() -> calendar_date:
    return datetime.now(tz=_GST_ZONE).date() - timedelta(days=1)


class GradingDashboardErrorCode(str, Enum):
    INVALID_DATE_WINDOW = "invalid_date_window"
    INVALID_LIMIT = "invalid_limit"


class GradingDashboardInsightSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class GradingDashboardErrorResponse(SchemaModel):
    code: GradingDashboardErrorCode = Field(
        description="Stable dashboard API error code.",
    )
    message: str = Field(min_length=1, description="Human-readable error summary.")
    details: list[str] = Field(
        default_factory=list,
        description="Optional validation details for the rejected dashboard request.",
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


class GradingDashboardDateWindow(SchemaModel):
    start_date: calendar_date = Field(
        description="Inclusive GST start date for the dashboard window."
    )
    end_date: calendar_date = Field(
        description="Inclusive GST end date for the dashboard window."
    )

    @model_validator(mode="after")
    def validate_date_order(self) -> "GradingDashboardDateWindow":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date.")
        return self


class GradingDashboardWindowQuery(SchemaModel):
    start_date: calendar_date | None = Field(
        default=None,
        description="Optional inclusive GST start date for the dashboard window.",
    )
    end_date: calendar_date | None = Field(
        default=None,
        description="Optional inclusive GST end date. Defaults to the previous GST day.",
    )

    @model_validator(mode="after")
    def resolve_and_validate_window(self) -> "GradingDashboardWindowQuery":
        settings = get_settings()
        previous_day = _previous_gst_day()

        resolved_end = self.end_date or previous_day
        resolved_start = self.start_date or (
            resolved_end - timedelta(days=settings.dashboard_default_window_days - 1)
        )

        if resolved_start > resolved_end:
            raise ValueError("start_date must be less than or equal to end_date.")
        if resolved_end > previous_day:
            raise ValueError("end_date must be on or before the previous GST day.")

        window_days = (resolved_end - resolved_start).days + 1
        if window_days > settings.dashboard_max_window_days:
            raise ValueError(
                "date window must not exceed the configured maximum dashboard range."
            )

        self.start_date = resolved_start
        self.end_date = resolved_end
        return self

    @property
    def date_window(self) -> GradingDashboardDateWindow:
        return GradingDashboardDateWindow(
            start_date=self.start_date,  # type: ignore[arg-type]
            end_date=self.end_date,  # type: ignore[arg-type]
        )


class GradingDashboardDailyTimelineQuery(SchemaModel):
    target_date: calendar_date | None = Field(
        default=None,
        description="GST target date for the Daily Timeline view.",
    )
    worst_performers_limit: int | None = Field(
        default=None,
        ge=1,
        description="Maximum worst-performer rows to return.",
    )

    @model_validator(mode="after")
    def resolve_and_validate(self) -> "GradingDashboardDailyTimelineQuery":
        settings = get_settings()
        previous_day = _previous_gst_day()

        resolved_target_date = self.target_date or previous_day
        resolved_limit = (
            self.worst_performers_limit
            or settings.dashboard_default_worst_performers_limit
        )

        if resolved_target_date > previous_day:
            raise ValueError("target_date must be on or before the previous GST day.")
        if resolved_limit > settings.dashboard_max_worst_performers_limit:
            raise ValueError(
                "worst_performers_limit must not exceed the configured maximum "
                "dashboard limit."
            )

        self.target_date = resolved_target_date
        self.worst_performers_limit = resolved_limit
        return self


class GradingDashboardFreshness(SchemaModel):
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
