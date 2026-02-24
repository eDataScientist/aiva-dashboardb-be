from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.router import api_router
from app.core import get_settings
from app.db import check_database_connection, close_database, configure_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_database(settings.database_url)
    await check_database_connection()
    app.state.settings = settings
    try:
        yield
    finally:
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

    @app.exception_handler(ValidationError)
    async def handle_pydantic_validation_error(
        _request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    app.include_router(api_router)
    return app


app = create_app()
