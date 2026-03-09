from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_account
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.analytics import (
    AnalyticsChannelFilter,
    AnalyticsFilterQuery,
    AnalyticsSummaryResponse,
    LeadConversionTrendResponse,
    MessageVolumeTrendResponse,
    PeakHoursResponse,
    QualityTrendResponse,
    TopIntentsQuery,
    TopIntentsResponse,
)
from app.services.analytics import (
    compute_lead_conversion_trend,
    compute_quality_trend,
    get_analytics_summary as _summary_service,
    get_message_volume_trend as _volume_trend_service,
    get_peak_hours as _peak_hours_service,
    get_top_intents as _top_intents_service,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Analytics summary KPIs",
)
async def get_analytics_summary(
    filters: Annotated[AnalyticsFilterQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalyticsSummaryResponse:
    return await _summary_service(
        session=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        channel=filters.channel.value,
    )


@router.get(
    "/message-volume-trend",
    response_model=MessageVolumeTrendResponse,
    summary="Daily message volume trend",
)
async def get_message_volume_trend(
    filters: Annotated[AnalyticsFilterQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageVolumeTrendResponse:
    return await _volume_trend_service(
        session=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        channel=filters.channel.value,
    )


@router.get(
    "/top-intents",
    response_model=TopIntentsResponse,
    summary="Top intents distribution",
)
async def get_top_intents(
    filters: Annotated[TopIntentsQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopIntentsResponse:
    return await _top_intents_service(
        session=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        channel=filters.channel.value,
        limit=filters.limit,
    )


@router.get(
    "/peak-hours",
    response_model=PeakHoursResponse,
    summary="Peak activity hours",
)
async def get_peak_hours(
    filters: Annotated[AnalyticsFilterQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PeakHoursResponse:
    return await _peak_hours_service(
        session=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        channel=filters.channel.value,
    )


@router.get(
    "/quality-trend",
    response_model=QualityTrendResponse,
    summary="AI quality trend",
)
async def get_quality_trend(
    filters: Annotated[AnalyticsFilterQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QualityTrendResponse:
    return await compute_quality_trend(
        session=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        channel=filters.channel,
    )


@router.get(
    "/lead-conversion-trend",
    response_model=LeadConversionTrendResponse,
    summary="Lead conversion trend",
)
async def get_lead_conversion_trend(
    filters: Annotated[AnalyticsFilterQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeadConversionTrendResponse:
    return await compute_lead_conversion_trend(
        session=db,
        start_date=filters.start_date,
        end_date=filters.end_date,
        channel=filters.channel,
    )
