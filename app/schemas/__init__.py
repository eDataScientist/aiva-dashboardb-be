"""Pydantic schemas for API request/response contracts."""

from app.schemas.analytics import (
    AnalyticsFilterQuery,
    AnalyticsSummaryResponse,
    LeadConversionTrendResponse,
    MessageVolumeTrendResponse,
    PeakHoursResponse,
    QualityTrendResponse,
    TopIntentsQuery,
    TopIntentsResponse,
)
from app.schemas.conversations import (
    ConversationListResponse,
    ConversationMessageItem,
    ConversationMessagesResponse,
    ConversationPathParams,
    ConversationsListQuery,
)

__all__ = [
    "AnalyticsFilterQuery",
    "AnalyticsSummaryResponse",
    "LeadConversionTrendResponse",
    "MessageVolumeTrendResponse",
    "PeakHoursResponse",
    "QualityTrendResponse",
    "TopIntentsQuery",
    "TopIntentsResponse",
    "ConversationListResponse",
    "ConversationMessageItem",
    "ConversationMessagesResponse",
    "ConversationPathParams",
    "ConversationsListQuery",
]
