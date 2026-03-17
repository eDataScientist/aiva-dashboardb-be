from __future__ import annotations

from datetime import date as calendar_date
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core import INTENT_CODE_TO_CATEGORY, INTENT_CODE_TO_LABEL
from app.schemas.analytics import SchemaModel
from app.schemas.grading_dashboard_common import GradingDashboardFreshness
from app.schemas.grading_metrics import GradingEscalationTypeSchema


class GradingDashboardDailyTimelineHourlyBucket(SchemaModel):
    hour: int = Field(ge=0, le=23)
    conversation_volume: int = Field(ge=0)
    resolution_rate_pct: float = Field(ge=0.0, le=100.0)


class GradingDashboardDailyTimelineHourSummary(SchemaModel):
    hour: int = Field(ge=0, le=23)
    conversation_volume: int = Field(ge=0)
    resolution_rate_pct: float = Field(ge=0.0, le=100.0)


class GradingDashboardDailyTimelineScatterPoint(SchemaModel):
    grade_id: UUID
    conversation_key: str = Field(min_length=1)
    satisfaction_score: float = Field(ge=0.0, le=10.0)
    frustration_score: float = Field(ge=0.0, le=10.0)
    resolution: bool | None = Field(default=None)
    loop_detected: bool | None = Field(default=None)

    @field_validator("conversation_key")
    @classmethod
    def validate_conversation_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("conversation_key must not be blank.")
        return normalized


class GradingDashboardDailyTimelineWorstPerformerRow(SchemaModel):
    grade_id: UUID
    conversation_key: str = Field(min_length=1)
    contact_label: str | None = Field(default=None)
    relevancy_score: int = Field(ge=1, le=10)
    accuracy_score: int = Field(ge=1, le=10)
    completeness_score: int = Field(ge=1, le=10)
    clarity_score: int = Field(ge=1, le=10)
    tone_score: int = Field(ge=1, le=10)
    satisfaction_score: int = Field(ge=1, le=10)
    frustration_score: int = Field(ge=1, le=10)
    resolution: bool | None = Field(default=None)
    escalation_type: GradingEscalationTypeSchema | None = Field(default=None)
    intent_code: str | None = Field(default=None)
    intent_label: str | None = Field(default=None)
    intent_category: str | None = Field(default=None)

    @field_validator(
        "conversation_key",
        "contact_label",
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
    def validate_intent_metadata_alignment(
        self,
    ) -> "GradingDashboardDailyTimelineWorstPerformerRow":
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


class GradingDashboardDailyTimelineResponse(SchemaModel):
    target_date: calendar_date
    hourly_buckets: list[GradingDashboardDailyTimelineHourlyBucket] = Field(
        default_factory=list
    )
    best_hour: GradingDashboardDailyTimelineHourSummary | None = Field(default=None)
    worst_hour: GradingDashboardDailyTimelineHourSummary | None = Field(default=None)
    scatter_points: list[GradingDashboardDailyTimelineScatterPoint] = Field(
        default_factory=list
    )
    worst_performers: list[GradingDashboardDailyTimelineWorstPerformerRow] = Field(
        default_factory=list
    )
    freshness: GradingDashboardFreshness
