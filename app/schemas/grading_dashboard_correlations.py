from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.core import (
    DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS,
    DASHBOARD_HEATMAP_SCORE_BUCKETS,
)
from app.schemas.analytics import SchemaModel
from app.schemas.grading_dashboard_common import (
    GradingDashboardDateWindow,
    GradingDashboardFreshness,
    GradingDashboardInsightSeverity,
)

_HEATMAP_BUCKET_LABELS = {
    label for label, _min_score, _max_score in DASHBOARD_HEATMAP_SCORE_BUCKETS
}
_HISTOGRAM_BUCKET_RANGES = {
    label: (min_score, max_score)
    for label, min_score, max_score in DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS
}


class GradingDashboardCorrelationHeatmapCell(SchemaModel):
    dimension_key: str = Field(min_length=1)
    dimension_label: str = Field(min_length=1)
    score_bucket: str = Field(min_length=1)
    conversation_count: int = Field(ge=0)
    avg_satisfaction_score: float = Field(ge=0.0, le=10.0)

    @field_validator("dimension_key", "dimension_label")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized

    @field_validator("score_bucket")
    @classmethod
    def validate_score_bucket(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in _HEATMAP_BUCKET_LABELS:
            raise ValueError("score_bucket must match a canonical dashboard heatmap bucket.")
        return normalized


class GradingDashboardCorrelationFunnelStep(SchemaModel):
    step_key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    count: int = Field(ge=0)

    @field_validator("step_key", "label")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized


class GradingDashboardCorrelationFrustrationHistogramBucket(SchemaModel):
    bucket_label: str = Field(min_length=1)
    min_score: int = Field(ge=1, le=10)
    max_score: int = Field(ge=1, le=10)
    count: int = Field(ge=0)
    share_pct: float = Field(ge=0.0, le=100.0)

    @field_validator("bucket_label")
    @classmethod
    def validate_bucket_label(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in _HISTOGRAM_BUCKET_RANGES:
            raise ValueError(
                "bucket_label must match a canonical dashboard histogram bucket."
            )
        return normalized

    @model_validator(mode="after")
    def validate_bucket_range(
        self,
    ) -> "GradingDashboardCorrelationFrustrationHistogramBucket":
        expected_range = _HISTOGRAM_BUCKET_RANGES[self.bucket_label]
        if (self.min_score, self.max_score) != expected_range:
            raise ValueError("min_score/max_score must match the canonical bucket range.")
        return self


class GradingDashboardCorrelationStoryCard(SchemaModel):
    code: str = Field(min_length=1)
    severity: GradingDashboardInsightSeverity
    title: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    metric_value: float | None = Field(default=None)
    explanation: str = Field(min_length=1)

    @field_validator("code", "title", "metric_key", "explanation")
    @classmethod
    def validate_non_blank_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("string fields must not be blank.")
        return normalized


class GradingDashboardCorrelationsResponse(SchemaModel):
    date_window: GradingDashboardDateWindow
    total_graded_customer_days: int = Field(ge=0)
    heatmap_cells: list[GradingDashboardCorrelationHeatmapCell] = Field(
        default_factory=list
    )
    failure_funnel: list[GradingDashboardCorrelationFunnelStep] = Field(
        default_factory=list
    )
    frustration_histogram: list[GradingDashboardCorrelationFrustrationHistogramBucket] = (
        Field(default_factory=list)
    )
    story_cards: list[GradingDashboardCorrelationStoryCard] = Field(
        default_factory=list
    )
    freshness: GradingDashboardFreshness
