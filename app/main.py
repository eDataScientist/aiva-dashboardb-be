from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core import get_settings
from app.db import check_database_connection, close_database, configure_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_database(settings.database_url)
    check_database_connection()
    app.state.settings = settings
    try:
        yield
    finally:
        close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    return app


app = create_app()
