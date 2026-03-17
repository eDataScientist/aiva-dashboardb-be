from __future__ import annotations

from datetime import date as calendar_date

from pydantic import Field, field_validator, model_validator

from app.core import INTENT_CODE_TO_CATEGORY, INTENT_CODE_TO_LABEL
from app.schemas.analytics import SchemaModel
from app.schemas.grading_dashboard_common import (
    GradingDashboardDateWindow,
    GradingDashboardFreshness,
    GradingDashboardInsightSeverity,
)
from app.schemas.grading_metrics import GradingEscalationTypeSchema


class GradingDashboardAgentPulseDimensionAverages(SchemaModel):
    relevancy: float = Field(ge=0.0, le=10.0)
    accuracy: float = Field(ge=0.0, le=10.0)
    completeness: float = Field(ge=0.0, le=10.0)
    clarity: float = Field(ge=0.0, le=10.0)
    tone: float = Field(ge=0.0, le=10.0)


class GradingDashboardAgentPulseHealth(SchemaModel):
    resolution_rate_pct: float = Field(ge=0.0, le=100.0)
    avg_repetition_score: float = Field(ge=0.0, le=10.0)
    loop_detected_rate_pct: float = Field(ge=0.0, le=100.0)


class GradingDashboardAgentPulseEscalationBreakdownItem(SchemaModel):
    escalation_type: GradingEscalationTypeSchema
    count: int = Field(ge=0)
    share_pct: float = Field(ge=0.0, le=100.0)


class GradingDashboardAgentPulseUserSignals(SchemaModel):
    avg_satisfaction_score: float = Field(ge=0.0, le=10.0)
    avg_frustration_score: float = Field(ge=0.0, le=10.0)
    user_relevancy_rate_pct: float = Field(ge=0.0, le=100.0)


class GradingDashboardAgentPulseTrendPoint(SchemaModel):
    date: calendar_date = Field(description="GST calendar date bucket.")
    overall_composite_score: float = Field(ge=0.0, le=10.0)
    satisfaction_score: float = Field(ge=0.0, le=10.0)
    frustration_score: float = Field(ge=0.0, le=10.0)


class GradingDashboardAgentPulseTopIntentTag(SchemaModel):
    intent_code: str = Field(min_length=1)
    intent_label: str = Field(min_length=1)
    intent_category: str = Field(min_length=1)
    count: int = Field(ge=0)

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
    def validate_intent_metadata_alignment(
        self,
    ) -> "GradingDashboardAgentPulseTopIntentTag":
        if self.intent_label != INTENT_CODE_TO_LABEL[self.intent_code]:
            raise ValueError("intent_label must match the canonical label.")
        if self.intent_category != INTENT_CODE_TO_CATEGORY[self.intent_code]:
            raise ValueError("intent_category must match the canonical category.")
        return self


class GradingDashboardAgentPulseAttentionSignal(SchemaModel):
    code: str = Field(min_length=1)
    severity: GradingDashboardInsightSeverity
    label: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    value: float | None = Field(default=None)
    message: str = Field(min_length=1)

    @field_validator("code", "label", "metric_key", "message")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized


class GradingDashboardAgentPulseResponse(SchemaModel):
    date_window: GradingDashboardDateWindow
    total_graded_customer_days: int = Field(ge=0)
    overall_composite_score: float = Field(ge=0.0, le=10.0)
    dimension_averages: GradingDashboardAgentPulseDimensionAverages
    health: GradingDashboardAgentPulseHealth
    escalation_breakdown: list[GradingDashboardAgentPulseEscalationBreakdownItem] = (
        Field(default_factory=list)
    )
    user_signals: GradingDashboardAgentPulseUserSignals
    trend_points: list[GradingDashboardAgentPulseTrendPoint] = Field(default_factory=list)
    top_intents: list[GradingDashboardAgentPulseTopIntentTag] = Field(default_factory=list)
    attention_signals: list[GradingDashboardAgentPulseAttentionSignal] = Field(
        default_factory=list
    )
    freshness: GradingDashboardFreshness
