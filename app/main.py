from asyncio import CancelledError
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.router import api_router
from app.core import get_settings
from app.db import check_database_connection, close_database, configure_database
from app.schemas.grading_dashboard_common import (
    GradingDashboardErrorCode,
    GradingDashboardErrorResponse,
)
from app.schemas.grading_monitoring import (
    MonitoringErrorCode,
    MonitoringErrorResponse,
)
from app.schemas.grading_runs import GradingRunErrorCode, GradingRunErrorResponse
from app.services.grading_scheduler import start_grading_scheduler, stop_grading_scheduler


_GRADING_RUNS_ROUTE_PATH = "/api/v1/grading/runs"
_MONITORING_ROUTE_PATH_PREFIX = "/api/v1/monitoring/conversations"
_DASHBOARD_ROUTE_PATH_PREFIX = "/api/v1/grading/dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_database(settings.database_url)
    await check_database_connection()
    app.state.settings = settings
    scheduler_handle = start_grading_scheduler(settings=settings)
    app.state.grading_scheduler_handle = scheduler_handle
    try:
        yield
    finally:
        try:
            await stop_grading_scheduler(getattr(app.state, "grading_scheduler_handle", None))
        except CancelledError:
            pass
        await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if _should_use_grading_run_validation_error(request):
            payload = GradingRunErrorResponse(
                code=GradingRunErrorCode.INVALID_DATE_WINDOW,
                message=_grading_run_validation_message(request),
                details=_normalize_validation_error_details(exc.errors()),
            ).model_dump()
            return JSONResponse(
                status_code=422,
                content=jsonable_encoder({"detail": payload}),
            )
        if _should_use_monitoring_validation_error(request):
            payload, status_code = _build_monitoring_validation_error(exc.errors())
            return JSONResponse(
                status_code=status_code,
                content=jsonable_encoder({"detail": payload}),
            )
        if _should_use_dashboard_validation_error(request):
            payload = _build_dashboard_validation_error(exc.errors())
            return JSONResponse(
                status_code=422,
                content=jsonable_encoder({"detail": payload}),
            )

        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    @app.exception_handler(ValidationError)
    async def handle_pydantic_validation_error(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        if _should_use_grading_run_validation_error(request):
            payload = GradingRunErrorResponse(
                code=GradingRunErrorCode.INVALID_DATE_WINDOW,
                message=_grading_run_validation_message(request),
                details=_normalize_validation_error_details(exc.errors()),
            ).model_dump()
            return JSONResponse(
                status_code=422,
                content=jsonable_encoder({"detail": payload}),
            )
        if _should_use_monitoring_validation_error(request):
            payload, status_code = _build_monitoring_validation_error(exc.errors())
            return JSONResponse(
                status_code=status_code,
                content=jsonable_encoder({"detail": payload}),
            )
        if _should_use_dashboard_validation_error(request):
            payload = _build_dashboard_validation_error(exc.errors())
            return JSONResponse(
                status_code=422,
                content=jsonable_encoder({"detail": payload}),
            )

        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    if settings.cors_allowed_origins:
        origins = [
            origin.strip()
            for origin in settings.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        if origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

    app.include_router(api_router)
    return app


def _should_use_grading_run_validation_error(request: Request) -> bool:
    normalized_path = request.url.path.rstrip("/") or "/"
    return normalized_path == _GRADING_RUNS_ROUTE_PATH and request.method in {
        "GET",
        "POST",
    }


def _should_use_monitoring_validation_error(request: Request) -> bool:
    normalized_path = request.url.path.rstrip("/") or "/"
    return normalized_path.startswith(_MONITORING_ROUTE_PATH_PREFIX) and request.method == "GET"


def _grading_run_validation_message(request: Request) -> str:
    if request.method == "GET":
        return "Grading run history request is invalid."
    return "Manual grading run request is invalid."


def _build_monitoring_validation_error(
    errors: list[dict[str, object]],
) -> tuple[MonitoringErrorResponse, int]:
    code, message, status_code = _classify_monitoring_validation_error(errors)
    payload = MonitoringErrorResponse(
        code=code,
        message=message,
        details=_normalize_validation_error_details(errors),
    )
    return payload, status_code


def _classify_monitoring_validation_error(
    errors: list[dict[str, object]],
) -> tuple[MonitoringErrorCode, str, int]:
    field_locs = {str(loc) for error in errors for loc in error.get("loc", ())}
    if "grade_id" in field_locs:
        return (
            MonitoringErrorCode.GRADE_NOT_FOUND,
            "Grade not found.",
            422,
        )
    if "intent_codes" in field_locs:
        return (
            MonitoringErrorCode.INVALID_INTENT_FILTER,
            "Invalid or unrecognized intent code filter.",
            422,
        )
    if "escalation_types" in field_locs:
        return (
            MonitoringErrorCode.INVALID_ESCALATION_FILTER,
            "Invalid or unrecognized escalation type filter.",
            422,
        )
    if "sort_by" in field_locs or "sort_direction" in field_locs:
        return (
            MonitoringErrorCode.INVALID_SORT,
            "Invalid monitoring sort field or direction.",
            422,
        )
    return (
        MonitoringErrorCode.INVALID_DATE_WINDOW,
        "Invalid or out-of-bounds monitoring date window.",
        422,
    )


def _should_use_dashboard_validation_error(request: Request) -> bool:
    normalized_path = request.url.path.rstrip("/") or "/"
    return normalized_path.startswith(_DASHBOARD_ROUTE_PATH_PREFIX) and request.method == "GET"


def _build_dashboard_validation_error(
    errors: list[dict[str, object]],
) -> GradingDashboardErrorResponse:
    code, message = _classify_dashboard_validation_error(errors)
    return GradingDashboardErrorResponse(
        code=code,
        message=message,
        details=_normalize_validation_error_details(errors),
    ).model_dump()


def _classify_dashboard_validation_error(
    errors: list[dict[str, object]],
) -> tuple[GradingDashboardErrorCode, str]:
    field_locs = {str(loc) for error in errors for loc in error.get("loc", ())}
    if "worst_performers_limit" in field_locs:
        return (
            GradingDashboardErrorCode.INVALID_LIMIT,
            "Invalid or out-of-bounds worst-performers limit.",
        )
    return (
        GradingDashboardErrorCode.INVALID_DATE_WINDOW,
        "Invalid or out-of-bounds dashboard date window.",
    )


def _normalize_validation_error_details(errors: list[dict[str, object]]) -> list[str]:
    details: list[str] = []
    for error in errors:
        message = str(error.get("msg", "Request validation failed.")).strip()
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ").strip()
        if message:
            details.append(message)
    return details or ["Request validation failed."]


app = create_app()
