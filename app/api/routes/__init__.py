from app.api.routes.accounts import router as accounts_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.grading_monitoring import router as grading_monitoring_router
from app.api.routes.grading_metrics import router as grading_metrics_router
from app.api.routes.grading_runs import router as grading_runs_router
from app.api.routes.health import router as health_router

__all__ = [
    "accounts_router",
    "analytics_router",
    "auth_router",
    "conversations_router",
    "grading_monitoring_router",
    "grading_metrics_router",
    "grading_runs_router",
    "health_router",
]
