from __future__ import annotations

from app.services import (
    MonitoringHighlightRuleSet,
    build_monitoring_detail_stmt,
    build_monitoring_history_stmt,
    build_monitoring_list_stmt,
    get_monitoring_highlight_defaults,
)


def test_monitoring_service_scaffold_exports_are_importable() -> None:
    defaults = get_monitoring_highlight_defaults()

    assert isinstance(defaults, MonitoringHighlightRuleSet)
    assert callable(build_monitoring_list_stmt)
    assert callable(build_monitoring_detail_stmt)
    assert callable(build_monitoring_history_stmt)
