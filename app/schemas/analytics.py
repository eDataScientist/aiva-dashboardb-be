from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyticsChannelFilter(str, Enum):
    ALL = "all"
    WHATSAPP = "whatsapp"
    WEB = "web"


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyticsFilterQuery(SchemaModel):
    start_date: Optional[datetime.date] = Field(
        default=None,
        description="Inclusive start date in GST-aligned reporting semantics.",
    )
    end_date: Optional[datetime.date] = Field(
        default=None,
        description="Inclusive end date in GST-aligned reporting semantics.",
    )
    channel: AnalyticsChannelFilter = Field(
        default=AnalyticsChannelFilter.ALL,
        description="Channel filter for analytics queries. Use 'all' for no channel restriction.",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "AnalyticsFilterQuery":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self


class TopIntentsQuery(AnalyticsFilterQuery):
    limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of ranked intents to return.",
    )


class DateValuePoint(SchemaModel):
    date: datetime.date = Field(description="GST calendar date bucket.")
    value: float = Field(description="Numeric metric value for the date bucket.")


class DateCountPoint(SchemaModel):
    date: datetime.date = Field(description="GST calendar date bucket.")
    count: int = Field(ge=0, description="Count value for the date bucket.")


class HourCountPoint(SchemaModel):
    hour: int = Field(ge=0, le=23, description="GST hour bucket (0-23).")
    count: int = Field(ge=0, description="Message count for the hour bucket.")


class IntentCountPoint(SchemaModel):
    intent: str = Field(
        description="Intent label. Null/blank source values should be normalized to 'Unknown'.",
    )
    count: int = Field(ge=0, description="Count of messages in this intent bucket.")
    share_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage share of the returned intent distribution.",
    )


class AnalyticsSummaryResponse(SchemaModel):
    total_messages: int = Field(ge=0)
    total_customers: int = Field(ge=0)
    inbound_messages: int = Field(ge=0)
    outbound_messages: int = Field(ge=0)
    escalated_customers: int = Field(ge=0)
    escalation_rate_pct: float = Field(ge=0.0, le=100.0)
    resolution_rate_pct: float = Field(ge=0.0, le=100.0)
    avg_engagement: float = Field(ge=0.0, description="Average messages per unique customer.")
    total_leads: int = Field(ge=0)
    lead_conversion_rate_pct: float = Field(
        ge=0.0,
        description=(
            "Lead conversion rate percentage. May exceed 100 if multiple lead events occur "
            "for the same customer within the selected range."
        ),
    )
    ai_quality_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Quicksheet formula: (Resolution Rate * 0.7) + (Lead Conversion Rate * 2.5), capped to 100.",
    )


class MessageVolumeTrendResponse(SchemaModel):
    points: list[DateCountPoint] = Field(
        default_factory=list,
        description="Daily message volume points sorted by date ascending (GST buckets).",
    )


class TopIntentsResponse(SchemaModel):
    points: list[IntentCountPoint] = Field(
        default_factory=list,
        description="Top ranked intents including 'Unknown' bucket when source intents are blank/null.",
    )


class PeakHoursResponse(SchemaModel):
    points: list[HourCountPoint] = Field(
        default_factory=list,
        description="Exactly 24 hourly buckets (0..23) in GST with zero-filled missing hours.",
    )


class QualityTrendResponse(SchemaModel):
    points: list[DateValuePoint] = Field(
        default_factory=list,
        description="Daily AI quality score trend using quicksheet chat-derived formula only.",
    )


class LeadConversionTrendPoint(SchemaModel):
    date: datetime.date = Field(description="GST calendar date bucket.")
    count: int = Field(ge=0, description="Lead conversion event count for the day.")
    rate_pct: float = Field(
        ge=0.0,
        description=(
            "Lead conversion rate using day-specific unique customers as denominator. "
            "Can exceed 100 when repeat lead events occur in the same day."
        ),
    )


class LeadConversionTrendResponse(SchemaModel):
    points: list[LeadConversionTrendPoint] = Field(
        default_factory=list,
        description="Daily lead conversion counts and rates sorted by date ascending.",
    )
