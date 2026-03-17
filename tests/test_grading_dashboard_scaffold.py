from __future__ import annotations

from app.schemas import GradingDashboardDailyTimelineQuery, GradingDashboardWindowQuery
from app.services import (
    build_grading_dashboard_agent_pulse_stmt,
    build_grading_dashboard_correlations_stmt,
    build_grading_dashboard_daily_timeline_stmt,
    get_grading_dashboard_agent_pulse,
    get_grading_dashboard_correlations,
    get_grading_dashboard_daily_timeline,
)


def test_dashboard_service_scaffold_exports_are_importable() -> None:
    window_query = GradingDashboardWindowQuery()
    timeline_query = GradingDashboardDailyTimelineQuery()

    assert window_query.date_window.start_date is not None
    assert timeline_query.target_date is not None
    assert callable(build_grading_dashboard_agent_pulse_stmt)
    assert callable(build_grading_dashboard_correlations_stmt)
    assert callable(build_grading_dashboard_daily_timeline_stmt)
    assert callable(get_grading_dashboard_agent_pulse)
    assert callable(get_grading_dashboard_correlations)
    assert callable(get_grading_dashboard_daily_timeline)
