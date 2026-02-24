from fastapi import APIRouter

from app.api.routes import analytics_router, conversations_router, health_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(analytics_router)
    router.include_router(conversations_router)
    return router


api_router = build_api_router()
