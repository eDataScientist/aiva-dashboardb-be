from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_account
from app.db.deps import get_db
from app.models.account import Account
from app.schemas.grading_runs import (
    GradingRunDetailResponse,
    GradingRunErrorCode,
    GradingRunErrorResponse,
    GradingRunListQuery,
    GradingRunListResponse,
    GradingRunTriggerRequest,
    GradingRunTriggerResponse,
)
from app.services.grading_batch import (
    prepare_manual_grading_run,
    run_grading_batch_in_background,
)
from app.services.grading_runs import (
    GradingRunConflictError,
    GradingRunNotFoundError,
    GradingRunPermissionError,
    GradingRunValidationError,
    get_grading_run_history_detail,
    list_grading_run_history,
)

router = APIRouter(prefix="/api/v1/grading/runs", tags=["grading-runs"])


def _raise_grading_run_error(
    *,
    status_code: int,
    code: GradingRunErrorCode,
    message: str,
    details: list[str] | None = None,
) -> HTTPException:
    payload = GradingRunErrorResponse(
        code=code,
        message=message,
        details=details or [],
    ).model_dump()
    return HTTPException(status_code=status_code, detail=payload)


@router.post(
    "",
    response_model=GradingRunTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a manual grading run",
)
async def trigger_grading_run(
    payload: GradingRunTriggerRequest,
    background_tasks: BackgroundTasks,
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingRunTriggerResponse:
    try:
        response, execution_request = await prepare_manual_grading_run(
            db,
            current_account=current_account,
            trigger_request=payload,
        )
    except GradingRunPermissionError as exc:
        raise _raise_grading_run_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code=GradingRunErrorCode.EXECUTION_NOT_ALLOWED,
            message=str(exc),
        ) from exc
    except GradingRunValidationError as exc:
        raise _raise_grading_run_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=GradingRunErrorCode.INVALID_DATE_WINDOW,
            message=exc.message,
            details=list(exc.details),
        ) from exc
    except GradingRunConflictError as exc:
        raise _raise_grading_run_error(
            status_code=status.HTTP_409_CONFLICT,
            code=GradingRunErrorCode.DUPLICATE_ACTIVE_WINDOW,
            message=str(exc),
        ) from exc

    background_tasks.add_task(
        run_grading_batch_in_background,
        response.run.id,
        execution_request,
    )
    return response


@router.get(
    "",
    response_model=GradingRunListResponse,
    summary="List grading run history",
)
async def list_runs(
    filters: Annotated[GradingRunListQuery, Depends()],
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingRunListResponse:
    try:
        return await list_grading_run_history(
            db,
            current_account=current_account,
            filters=filters,
        )
    except GradingRunPermissionError as exc:
        raise _raise_grading_run_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code=GradingRunErrorCode.EXECUTION_NOT_ALLOWED,
            message=str(exc),
        ) from exc


@router.get(
    "/{run_id}",
    response_model=GradingRunDetailResponse,
    summary="Get one grading run with item history",
)
async def get_run_detail(
    run_id: UUID,
    current_account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GradingRunDetailResponse:
    try:
        return await get_grading_run_history_detail(
            db,
            current_account=current_account,
            run_id=run_id,
        )
    except GradingRunPermissionError as exc:
        raise _raise_grading_run_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code=GradingRunErrorCode.EXECUTION_NOT_ALLOWED,
            message=str(exc),
        ) from exc
    except GradingRunNotFoundError as exc:
        raise _raise_grading_run_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=GradingRunErrorCode.RUN_NOT_FOUND,
            message=str(exc),
        ) from exc
