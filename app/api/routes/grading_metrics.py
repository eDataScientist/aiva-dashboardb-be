from __future__ import annotations

from datetime import date as calendar_date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_account
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.grading_metrics import (
    GradingIntentDistributionResponse,
    GradingIntentTrendResponse,
    GradingMetricsErrorCode,
    GradingMetricsErrorResponse,
    GradingMetricsIntentTrendQuery,
    GradingMetricsSummaryResponse,
    GradingMetricsWindowQuery,
    GradingOutcomeTrendResponse,
    GradingScoreTrendResponse,
)
from app.services.grading_metrics import (
    get_grading_metrics_summary,
    get_grading_outcome_trends,
    get_grading_score_trends,
    get_intent_distribution,
    get_intent_trend,
)

router = APIRouter(prefix="/api/v1/grading/metrics", tags=["grading-metrics"])


def _raise_metrics_error(
    *,
    status_code: int,
    code: GradingMetricsErrorCode,
    message: str,
    details: list[str] | None = None,
) -> HTTPException:
    payload = GradingMetricsErrorResponse(
        code=code,
        message=message,
        details=details or [],
    ).model_dump()
    return HTTPException(status_code=status_code, detail=payload)


async def _parse_window_query(
    start_date: calendar_date | None = Query(default=None),
    end_date: calendar_date | None = Query(default=None),
) -> GradingMetricsWindowQuery:
    try:
        return GradingMetricsWindowQuery(start_date=start_date, end_date=end_date)
    except ValidationError as exc:
        details = [err["msg"] for err in exc.errors()]
        raise _raise_metrics_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=GradingMetricsErrorCode.INVALID_DATE_WINDOW,
            message="Invalid or out-of-bounds date window.",
            details=details,
        ) from exc


async def _parse_intent_trend_query(
    start_date: calendar_date | None = Query(default=None),
    end_date: calendar_date | None = Query(default=None),
    intent_codes: list[str] = Query(default=[]),
) -> GradingMetricsIntentTrendQuery:
    try:
        return GradingMetricsIntentTrendQuery(
            start_date=start_date,
            end_date=end_date,
            intent_codes=intent_codes,
        )
    except ValidationError as exc:
        details = [err["msg"] for err in exc.errors()]
        field_locs = {loc for err in exc.errors() for loc in err.get("loc", ())}
        if "intent_codes" in field_locs:
            code = GradingMetricsErrorCode.INVALID_INTENT_FILTER
            message = "Invalid or unrecognized intent code filter."
        else:
            code = GradingMetricsErrorCode.INVALID_DATE_WINDOW
            message = "Invalid or out-of-bounds date window."
        raise _raise_metrics_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            message=message,
            details=details,
        ) from exc


@router.get(
    "/summary",
    response_model=GradingMetricsSummaryResponse,
    summary="Get AI grading quality summary for a date window",
)
async def get_metrics_summary(
    query: Annotated[GradingMetricsWindowQuery, Depends(_parse_window_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingMetricsSummaryResponse:
    return await get_grading_metrics_summary(db, query)


@router.get(
    "/score-trends",
    response_model=GradingScoreTrendResponse,
    summary="Get daily score trends for a date window",
)
async def get_score_trends(
    query: Annotated[GradingMetricsWindowQuery, Depends(_parse_window_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingScoreTrendResponse:
    return await get_grading_score_trends(db, query)


@router.get(
    "/outcome-trends",
    response_model=GradingOutcomeTrendResponse,
    summary="Get daily outcome-rate trends for a date window",
)
async def get_outcome_trends(
    query: Annotated[GradingMetricsWindowQuery, Depends(_parse_window_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingOutcomeTrendResponse:
    return await get_grading_outcome_trends(db, query)


@router.get(
    "/intents/distribution",
    response_model=GradingIntentDistributionResponse,
    summary="Get canonical intent distribution for a date window",
)
async def get_intents_distribution(
    query: Annotated[GradingMetricsWindowQuery, Depends(_parse_window_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingIntentDistributionResponse:
    return await get_intent_distribution(db, query)


@router.get(
    "/intents/trend",
    response_model=GradingIntentTrendResponse,
    summary="Get daily intent trend series for a date window",
)
async def get_intents_trend(
    query: Annotated[GradingMetricsIntentTrendQuery, Depends(_parse_intent_trend_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingIntentTrendResponse:
    return await get_intent_trend(db, query)
