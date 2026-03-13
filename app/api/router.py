from fastapi import APIRouter

from app.api.routes import (
    accounts_router,
    analytics_router,
    auth_router,
    conversations_router,
    grading_metrics_router,
    grading_runs_router,
    health_router,
)


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(auth_router)
    router.include_router(accounts_router)
    router.include_router(analytics_router)
    router.include_router(conversations_router)
    router.include_router(grading_runs_router)
    router.include_router(grading_metrics_router)
    return router


api_router = build_api_router()
