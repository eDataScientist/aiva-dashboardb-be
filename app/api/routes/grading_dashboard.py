from __future__ import annotations

from datetime import date as calendar_date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_account
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.grading_dashboard_agent_pulse import (
    GradingDashboardAgentPulseResponse,
)
from app.schemas.grading_dashboard_common import (
    GradingDashboardDailyTimelineQuery,
    GradingDashboardErrorCode,
    GradingDashboardErrorResponse,
    GradingDashboardWindowQuery,
)
from app.schemas.grading_dashboard_correlations import (
    GradingDashboardCorrelationsResponse,
)
from app.schemas.grading_dashboard_daily_timeline import (
    GradingDashboardDailyTimelineResponse,
)
from app.services.grading_dashboard_agent_pulse import (
    get_grading_dashboard_agent_pulse,
)
from app.services.grading_dashboard_correlations import (
    get_grading_dashboard_correlations,
)
from app.services.grading_dashboard_daily_timeline import (
    get_grading_dashboard_daily_timeline,
)

router = APIRouter(
    prefix="/api/v1/grading/dashboard",
    tags=["grading-dashboard"],
)


def _raise_dashboard_error(
    *,
    status_code: int,
    code: GradingDashboardErrorCode,
    message: str,
    details: list[str] | None = None,
) -> HTTPException:
    payload = GradingDashboardErrorResponse(
        code=code,
        message=message,
        details=details or [],
    ).model_dump()
    return HTTPException(status_code=status_code, detail=payload)


def _classify_dashboard_query_error(
    exc: ValidationError,
) -> tuple[GradingDashboardErrorCode, str]:
    field_locs = {loc for err in exc.errors() for loc in err.get("loc", ())}
    if "worst_performers_limit" in field_locs:
        return (
            GradingDashboardErrorCode.INVALID_LIMIT,
            "Invalid or out-of-bounds worst-performers limit.",
        )
    # Model-level validators produce empty loc tuples, so fall back to message
    # content matching for the over-max worst_performers_limit path.
    for err in exc.errors():
        if "worst_performers_limit" in str(err.get("msg", "")):
            return (
                GradingDashboardErrorCode.INVALID_LIMIT,
                "Invalid or out-of-bounds worst-performers limit.",
            )
    return (
        GradingDashboardErrorCode.INVALID_DATE_WINDOW,
        "Invalid or out-of-bounds dashboard date window.",
    )


async def _parse_dashboard_window_query(
    start_date: calendar_date | None = Query(default=None),
    end_date: calendar_date | None = Query(default=None),
) -> GradingDashboardWindowQuery:
    try:
        return GradingDashboardWindowQuery(start_date=start_date, end_date=end_date)
    except ValidationError as exc:
        details = [err["msg"] for err in exc.errors()]
        raise _raise_dashboard_error(
            status_code=422,
            code=GradingDashboardErrorCode.INVALID_DATE_WINDOW,
            message="Invalid or out-of-bounds dashboard date window.",
            details=details,
        ) from exc


async def _parse_daily_timeline_query(
    target_date: calendar_date | None = Query(default=None),
    worst_performers_limit: int | None = Query(default=None, ge=1),
) -> GradingDashboardDailyTimelineQuery:
    try:
        return GradingDashboardDailyTimelineQuery(
            target_date=target_date,
            worst_performers_limit=worst_performers_limit,
        )
    except ValidationError as exc:
        code, message = _classify_dashboard_query_error(exc)
        details = [err["msg"] for err in exc.errors()]
        raise _raise_dashboard_error(
            status_code=422,
            code=code,
            message=message,
            details=details,
        ) from exc


@router.get(
    "/agent-pulse",
    response_model=GradingDashboardAgentPulseResponse,
    summary="Get Agent Pulse dashboard view for a date window",
)
async def get_dashboard_agent_pulse(
    query: Annotated[GradingDashboardWindowQuery, Depends(_parse_dashboard_window_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingDashboardAgentPulseResponse:
    return await get_grading_dashboard_agent_pulse(db, query)


@router.get(
    "/correlations",
    response_model=GradingDashboardCorrelationsResponse,
    summary="Get Correlations dashboard view for a date window",
)
async def get_dashboard_correlations(
    query: Annotated[GradingDashboardWindowQuery, Depends(_parse_dashboard_window_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingDashboardCorrelationsResponse:
    return await get_grading_dashboard_correlations(db, query)


@router.get(
    "/daily-timeline",
    response_model=GradingDashboardDailyTimelineResponse,
    summary="Get Daily Timeline dashboard view for a target date",
)
async def get_dashboard_daily_timeline(
    query: Annotated[GradingDashboardDailyTimelineQuery, Depends(_parse_daily_timeline_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingDashboardDailyTimelineResponse:
    return await get_grading_dashboard_daily_timeline(db, query)
