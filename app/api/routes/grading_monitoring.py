from __future__ import annotations

from datetime import date as calendar_date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_account
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.grading_monitoring import (
    MonitoringConversationDetailResponse,
    MonitoringConversationListQuery,
    MonitoringConversationListResponse,
    MonitoringErrorCode,
    MonitoringErrorResponse,
)
from app.services.grading_monitoring import (
    MonitoringConversationNotFoundError,
    get_monitoring_conversation_detail,
    get_monitoring_conversation_list,
)

router = APIRouter(
    prefix="/api/v1/monitoring/conversations",
    tags=["grading-monitoring"],
)


def _raise_monitoring_error(
    *,
    status_code: int,
    code: MonitoringErrorCode,
    message: str,
    details: list[str] | None = None,
) -> HTTPException:
    payload = MonitoringErrorResponse(
        code=code,
        message=message,
        details=details or [],
    ).model_dump()
    return HTTPException(status_code=status_code, detail=payload)


def _classify_list_query_error(exc: ValidationError) -> tuple[MonitoringErrorCode, str]:
    field_locs = {loc for err in exc.errors() for loc in err.get("loc", ())}
    if "intent_codes" in field_locs:
        return (
            MonitoringErrorCode.INVALID_INTENT_FILTER,
            "Invalid or unrecognized intent code filter.",
        )
    if "escalation_types" in field_locs:
        return (
            MonitoringErrorCode.INVALID_ESCALATION_FILTER,
            "Invalid or unrecognized escalation type filter.",
        )
    if "sort_by" in field_locs or "sort_direction" in field_locs:
        return (
            MonitoringErrorCode.INVALID_SORT,
            "Invalid monitoring sort field or direction.",
        )
    return (
        MonitoringErrorCode.INVALID_DATE_WINDOW,
        "Invalid or out-of-bounds monitoring date window.",
    )


async def _parse_monitoring_list_query(
    start_date: calendar_date | None = Query(default=None),
    end_date: calendar_date | None = Query(default=None),
    resolution: bool | None = Query(default=None),
    escalation_types: list[str] = Query(default=[]),
    frustration_min: int | None = Query(default=None),
    accuracy_max: int | None = Query(default=None),
    intent_codes: list[str] = Query(default=[]),
    sort_by: str | None = Query(default=None),
    sort_direction: str = Query(default="desc"),
    limit: int | None = Query(default=None),
    offset: int = Query(default=0),
) -> MonitoringConversationListQuery:
    try:
        return MonitoringConversationListQuery(
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            escalation_types=escalation_types,
            frustration_min=frustration_min,
            accuracy_max=accuracy_max,
            intent_codes=intent_codes,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset,
        )
    except ValidationError as exc:
        code, message = _classify_list_query_error(exc)
        details = [err["msg"] for err in exc.errors()]
        raise _raise_monitoring_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=code,
            message=message,
            details=details,
        ) from exc


@router.get(
    "",
    response_model=MonitoringConversationListResponse,
    summary="List monitored customer-day conversations",
)
async def list_monitoring_conversations(
    query: Annotated[MonitoringConversationListQuery, Depends(_parse_monitoring_list_query)],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonitoringConversationListResponse:
    return await get_monitoring_conversation_list(db, query)


@router.get(
    "/{grade_id}",
    response_model=MonitoringConversationDetailResponse,
    summary="Get monitored customer-day conversation detail",
)
async def get_monitoring_conversation(
    grade_id: UUID,
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonitoringConversationDetailResponse:
    try:
        detail = await get_monitoring_conversation_detail(db, grade_id)
    except MonitoringConversationNotFoundError as exc:
        raise _raise_monitoring_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=MonitoringErrorCode.GRADE_NOT_FOUND,
            message=str(exc),
        ) from exc

    return MonitoringConversationDetailResponse(detail=detail)
