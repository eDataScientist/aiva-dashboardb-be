from asyncio import CancelledError
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.router import api_router
from app.core import get_settings
from app.db import check_database_connection, close_database, configure_database
from app.schemas.grading_runs import GradingRunErrorCode, GradingRunErrorResponse
from app.services.grading_scheduler import start_grading_scheduler, stop_grading_scheduler


_GRADING_RUNS_ROUTE_PATH = "/api/v1/grading/runs"


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

        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    app.include_router(api_router)
    return app


def _should_use_grading_run_validation_error(request: Request) -> bool:
    normalized_path = request.url.path.rstrip("/") or "/"
    return normalized_path == _GRADING_RUNS_ROUTE_PATH and request.method in {
        "GET",
        "POST",
    }


def _grading_run_validation_message(request: Request) -> str:
    if request.method == "GET":
        return "Grading run history request is invalid."
    return "Manual grading run request is invalid."


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
