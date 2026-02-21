from fastapi import APIRouter

from app.api.routes import health_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    return router


api_router = build_api_router()

