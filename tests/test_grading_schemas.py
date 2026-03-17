from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.grading import GradingOutput, GradingParseError
from app.schemas.grading_dashboard_agent_pulse import (
    GradingDashboardAgentPulseResponse,
)
from app.schemas.grading_dashboard_common import (
    GradingDashboardDailyTimelineQuery,
    GradingDashboardErrorResponse,
    GradingDashboardWindowQuery,
)
from app.schemas.grading_dashboard_correlations import (
    GradingDashboardCorrelationsResponse,
)
from app.schemas.grading_dashboard_daily_timeline import (
    GradingDashboardDailyTimelineResponse,
)
from app.schemas.grading_metrics import (
    GradingIntentDistributionItem,
    GradingMetricsErrorResponse,
    GradingMetricsIntentTrendQuery,
    GradingMetricsWindowQuery,
    GradingMetricsSummaryResponse,
)
from app.schemas.grading_monitoring import (
    MonitoringConversationDetailResponse,
    MonitoringConversationListQuery,
    MonitoringConversationListResponse,
    MonitoringConversationSummary,
    MonitoringErrorResponse,
)
from app.schemas.grading_prompts import (
    PromptDomain,
    PromptPackManifest,
    PromptPackPartialOutputs,
    PromptTemplateSpec,
)
from app.schemas.grading_runs import (
    GradingRunErrorResponse,
    GradingRunTriggerRequest,
    GradingRunSummary,
)


def _valid_grading_output_payload() -> dict[str, object]:
    return {
        "relevancy_score": 8,
        "relevancy_reasoning": "The assistant stayed focused on the policy question.",
        "accuracy_score": 7,
        "accuracy_reasoning": "The response was mostly correct with minor gaps.",
        "completeness_score": 8,
        "completeness_reasoning": "The answer covered the main requested details.",
        "clarity_score": 9,
        "clarity_reasoning": "The assistant used clear and direct wording.",
        "tone_score": 9,
        "tone_reasoning": "The tone remained professional throughout the exchange.",
        "resolution": True,
        "resolution_reasoning": "The customer received a complete answer and did not reopen the issue.",
        "repetition_score": 8,
        "repetition_reasoning": "The assistant avoided repeating the same steps.",
        "loop_detected": False,
        "loop_detected_reasoning": "The conversation progressed without circular replies.",
        "satisfaction_score": 8,
        "satisfaction_reasoning": "The customer language suggested confidence in the outcome.",
        "frustration_score": 2,
        "frustration_reasoning": "There were no strong indicators of frustration.",
        "user_relevancy": True,
        "user_relevancy_reasoning": "The interaction was a genuine insurance support request.",
        "escalation_occurred": False,
        "escalation_occurred_reasoning": "The assistant completed the interaction without handoff.",
        "escalation_type": "None",
        "escalation_type_reasoning": "No human handoff was needed.",
        "intent_code": "policy_inquiry",
        "intent_label": "Policy Inquiry",
        "intent_reasoning": "The user primarily asked for information about an existing policy.",
    }


def test_grading_output_accepts_valid_payload() -> None:
    payload = GradingOutput(**_valid_grading_output_payload())
    assert payload.intent_code == "policy_inquiry"
    assert payload.escalation_type.value == "None"


def test_grading_output_rejects_mismatched_intent_label() -> None:
    invalid_payload = _valid_grading_output_payload()
    invalid_payload["intent_label"] = "Claims Follow-up"

    with pytest.raises(ValidationError):
        GradingOutput(**invalid_payload)


def test_grading_output_rejects_blank_reasoning() -> None:
    invalid_payload = _valid_grading_output_payload()
    invalid_payload["accuracy_reasoning"] = "   "

    with pytest.raises(ValidationError):
        GradingOutput(**invalid_payload)


def test_grading_output_rejects_string_score_inputs() -> None:
    invalid_payload = _valid_grading_output_payload()
    invalid_payload["relevancy_score"] = "8"

    with pytest.raises(ValidationError):
        GradingOutput(**invalid_payload)


def test_grading_output_rejects_string_boolean_inputs() -> None:
    invalid_payload = _valid_grading_output_payload()
    invalid_payload["resolution"] = "true"

    with pytest.raises(ValidationError):
        GradingOutput(**invalid_payload)


def test_grading_parse_error_rejects_blank_message() -> None:
    with pytest.raises(ValidationError):
        GradingParseError(
            code="invalid_json",
            message="   ",
        )


def test_grading_run_trigger_request_accepts_single_grade_date() -> None:
    request = GradingRunTriggerRequest(grade_date="2026-03-11")
    assert request.target_start_date.isoformat() == "2026-03-11"
    assert request.target_end_date.isoformat() == "2026-03-11"
    assert request.rerun_existing is False


def test_grading_run_trigger_request_rejects_mixed_date_shapes() -> None:
    with pytest.raises(ValidationError):
        GradingRunTriggerRequest(
            grade_date="2026-03-11",
            start_date="2026-03-10",
            end_date="2026-03-11",
        )


def test_grading_run_summary_rejects_blank_provider_snapshot() -> None:
    with pytest.raises(ValidationError):
        GradingRunSummary(
            id="df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            trigger_type="manual",
            run_mode="backfill",
            status="queued",
            target_start_date="2026-03-10",
            target_end_date="2026-03-11",
            rerun_existing=False,
            provider="   ",
            model="mock-grade-v1",
            prompt_version="v1",
            candidate_count=0,
            attempted_count=0,
            success_count=0,
            skipped_existing_count=0,
            empty_transcript_count=0,
            provider_error_count=0,
            parse_error_count=0,
            created_at="2026-03-12T10:00:00",
            updated_at="2026-03-12T10:00:00",
        )


def test_grading_run_error_response_rejects_blank_details() -> None:
    with pytest.raises(ValidationError):
        GradingRunErrorResponse(
            code="invalid_date_window",
            message="Date range is invalid.",
            details=["   "],
        )


def test_prompt_pack_manifest_accepts_ordered_unique_prompt_specs() -> None:
    manifest = PromptPackManifest(
        version="v1",
        prompt_order=tuple(PromptDomain),
        prompt_templates=(
            PromptTemplateSpec(
                prompt_key=PromptDomain.AI_PERFORMANCE,
                template_file="ai_performance_judge.md",
                output_fields=("relevancy_score",),
                include_system_prompt=True,
                required_placeholders=("conversation", "system_prompt"),
            ),
            PromptTemplateSpec(
                prompt_key=PromptDomain.CONVERSATION_HEALTH,
                template_file="conversation_health.md",
                output_fields=("resolution",),
                required_placeholders=("conversation",),
            ),
            PromptTemplateSpec(
                prompt_key=PromptDomain.USER_SIGNALS,
                template_file="user-signals.md",
                output_fields=("satisfaction_score",),
                required_placeholders=("conversation",),
            ),
            PromptTemplateSpec(
                prompt_key=PromptDomain.ESCALATION,
                template_file="escalation.md",
                output_fields=("escalation_occurred",),
                include_system_prompt=True,
                required_placeholders=("conversation", "system_prompt"),
            ),
            PromptTemplateSpec(
                prompt_key=PromptDomain.INTENT,
                template_file="intent.md",
                output_fields=("intent_label", "intent_reasoning"),
                required_placeholders=("conversation",),
            ),
        ),
    )

    assert manifest.version == "v1"
    assert manifest.prompt_templates[0].prompt_key == PromptDomain.AI_PERFORMANCE


def test_prompt_pack_manifest_rejects_incomplete_prompt_domain_set() -> None:
    with pytest.raises(ValidationError):
        PromptPackManifest(
            version="v1",
            prompt_order=(PromptDomain.AI_PERFORMANCE, PromptDomain.INTENT),
            prompt_templates=(
                PromptTemplateSpec(
                    prompt_key=PromptDomain.AI_PERFORMANCE,
                    template_file="ai_performance_judge.md",
                    output_fields=("relevancy_score",),
                    include_system_prompt=True,
                    required_placeholders=("conversation", "system_prompt"),
                ),
                PromptTemplateSpec(
                    prompt_key=PromptDomain.INTENT,
                    template_file="intent.md",
                    output_fields=("intent_label", "intent_reasoning"),
                    required_placeholders=("conversation",),
                ),
            ),
        )


def test_prompt_template_spec_rejects_missing_system_prompt_placeholder() -> None:
    with pytest.raises(ValidationError):
        PromptTemplateSpec(
            prompt_key=PromptDomain.AI_PERFORMANCE,
            template_file="ai_performance_judge.md",
            output_fields=("relevancy_score",),
            include_system_prompt=True,
            required_placeholders=("conversation",),
        )


def test_prompt_pack_partial_outputs_require_all_domains() -> None:
    payload = _valid_grading_output_payload()

    partial_outputs = PromptPackPartialOutputs(
        ai_performance={
            "relevancy_score": payload["relevancy_score"],
            "relevancy_reasoning": payload["relevancy_reasoning"],
            "accuracy_score": payload["accuracy_score"],
            "accuracy_reasoning": payload["accuracy_reasoning"],
            "completeness_score": payload["completeness_score"],
            "completeness_reasoning": payload["completeness_reasoning"],
            "clarity_score": payload["clarity_score"],
            "clarity_reasoning": payload["clarity_reasoning"],
            "tone_score": payload["tone_score"],
            "tone_reasoning": payload["tone_reasoning"],
        },
        conversation_health={
            "resolution": payload["resolution"],
            "resolution_reasoning": payload["resolution_reasoning"],
            "repetition_score": payload["repetition_score"],
            "repetition_reasoning": payload["repetition_reasoning"],
            "loop_detected": payload["loop_detected"],
            "loop_detected_reasoning": payload["loop_detected_reasoning"],
        },
        user_signals={
            "satisfaction_score": payload["satisfaction_score"],
            "satisfaction_reasoning": payload["satisfaction_reasoning"],
            "frustration_score": payload["frustration_score"],
            "frustration_reasoning": payload["frustration_reasoning"],
            "user_relevancy": payload["user_relevancy"],
            "user_relevancy_reasoning": payload["user_relevancy_reasoning"],
        },
        escalation={
            "escalation_occurred": payload["escalation_occurred"],
            "escalation_occurred_reasoning": payload["escalation_occurred_reasoning"],
            "escalation_type": payload["escalation_type"],
            "escalation_type_reasoning": payload["escalation_type_reasoning"],
        },
        intent={
            "intent_label": payload["intent_label"],
            "intent_reasoning": payload["intent_reasoning"],
        },
    )

    assert partial_outputs.intent.intent_label == "Policy Inquiry"


def test_grading_metrics_window_query_defaults_to_previous_gst_window() -> None:
    query = GradingMetricsWindowQuery()
    assert query.start_date is not None
    assert query.end_date is not None
    assert (query.end_date - query.start_date).days == 29


def test_grading_metrics_window_query_rejects_future_end_date() -> None:
    with pytest.raises(ValidationError):
        GradingMetricsWindowQuery(end_date="2099-01-01")


def test_grading_metrics_window_query_rejects_excessive_span() -> None:
    with pytest.raises(ValidationError):
        GradingMetricsWindowQuery(
            start_date="2025-01-01",
            end_date="2026-02-01",
        )


def test_grading_metrics_intent_trend_query_normalizes_and_deduplicates_codes() -> None:
    query = GradingMetricsIntentTrendQuery(
        intent_codes=[" policy_inquiry ", "policy_inquiry", "complaint"],
    )
    assert query.intent_codes == ["policy_inquiry", "complaint"]


def test_grading_metrics_intent_distribution_item_rejects_mismatched_category() -> None:
    with pytest.raises(ValidationError):
        GradingIntentDistributionItem(
            intent_code="policy_inquiry",
            intent_label="Policy Inquiry",
            intent_category="Claims Related",
            count=1,
            share_pct=100.0,
        )


def test_grading_metrics_error_response_rejects_blank_detail_items() -> None:
    with pytest.raises(ValidationError):
        GradingMetricsErrorResponse(
            code="invalid_date_window",
            message="Window is invalid.",
            details=["   "],
        )


def test_grading_metrics_summary_response_accepts_canonical_payload() -> None:
    response = GradingMetricsSummaryResponse(
        date_window={"start_date": "2026-02-10", "end_date": "2026-03-11"},
        total_graded_customer_days=12,
        average_scores={
            "relevancy": 8.1,
            "accuracy": 7.9,
            "completeness": 8.0,
            "clarity": 8.2,
            "tone": 8.4,
            "repetition": 7.6,
            "satisfaction": 7.8,
            "frustration": 2.1,
        },
        outcome_rates={
            "resolution_rate_pct": 80.0,
            "loop_detected_rate_pct": 5.0,
            "non_genuine_rate_pct": 10.0,
            "escalation_rate_pct": 12.5,
            "escalation_failure_rate_pct": 4.0,
        },
        escalation_breakdown=[
            {"escalation_type": "Natural", "count": 1, "share_pct": 8.3},
            {"escalation_type": "Failure", "count": 1, "share_pct": 8.3},
            {"escalation_type": "None", "count": 10, "share_pct": 83.4},
        ],
        freshness={
            "latest_successful_run_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            "latest_successful_window_end_date": "2026-03-11",
            "latest_successful_run_finished_at": "2026-03-12T10:00:00",
        },
    )

    assert response.average_scores.relevancy == 8.1
    assert response.escalation_breakdown[0].escalation_type.value == "Natural"


def test_monitoring_conversation_list_query_defaults_to_previous_gst_day() -> None:
    query = MonitoringConversationListQuery()

    assert query.start_date is not None
    assert query.end_date is not None
    assert query.start_date == query.end_date
    assert query.limit == 50
    assert query.offset == 0
    assert query.sort_by is None
    assert query.sort_direction == "desc"


def test_monitoring_conversation_list_query_rejects_unsupported_sort_field() -> None:
    with pytest.raises(ValidationError):
        MonitoringConversationListQuery(sort_by="grade_date")


def test_monitoring_conversation_list_query_normalizes_and_deduplicates_filters() -> None:
    query = MonitoringConversationListQuery(
        intent_codes=[" policy_inquiry ", "policy_inquiry", "complaint"],
        escalation_types=[" failure ", "Failure", "None"],
    )

    assert query.intent_codes == ["policy_inquiry", "complaint"]
    assert query.escalation_types == ["Failure", "None"]


def test_monitoring_conversation_summary_requires_canonical_metadata_alignment() -> None:
    with pytest.raises(ValidationError):
        MonitoringConversationSummary(
            grade_id="df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            grade_date="2026-03-11",
            conversation_key="phone:+971500000001",
            contact_name="Jane Doe",
            latest_message_preview="Customer needs help with policy details.",
            latest_message_at="2026-03-11T12:00:00",
            message_count=4,
            intent_code="policy_inquiry",
            intent_label="Claims Submission",
            intent_category="Policy Related",
            resolution=True,
            escalation_type="None",
            frustration_score=2,
            accuracy_score=8,
            highlights=[],
        )


def test_monitoring_conversation_list_response_accepts_canonical_payload() -> None:
    response = MonitoringConversationListResponse(
        date_window={"start_date": "2026-03-11", "end_date": "2026-03-11"},
        total=1,
        limit=50,
        offset=0,
        items=[
            {
                "grade_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
                "grade_date": "2026-03-11",
                "conversation_key": "phone:+971500000001",
                "contact_name": "Jane Doe",
                "latest_message_preview": "Customer needs help with policy details.",
                "latest_message_at": "2026-03-11T12:00:00",
                "message_count": 4,
                "intent_code": "policy_inquiry",
                "intent_label": "Policy Inquiry",
                "intent_category": "Policy Related",
                "resolution": True,
                "escalation_type": "None",
                "frustration_score": 2,
                "accuracy_score": 8,
                "highlights": [
                    {"code": "frustration_high", "label": "High Frustration"}
                ],
            }
        ],
        freshness={
            "latest_successful_run_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            "latest_successful_window_end_date": "2026-03-11",
            "latest_successful_run_finished_at": "2026-03-12T10:00:00",
        },
    )

    assert response.items[0].intent_label == "Policy Inquiry"
    assert response.items[0].highlights[0].code == "frustration_high"


def test_monitoring_conversation_detail_response_accepts_grouped_payload() -> None:
    response = MonitoringConversationDetailResponse(
        detail={
            "grade_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            "grade_date": "2026-03-11",
            "conversation_key": "phone:+971500000001",
            "contact_name": "Jane Doe",
            "intent_code": "policy_inquiry",
            "intent_label": "Policy Inquiry",
            "intent_category": "Policy Related",
            "resolution": True,
            "escalation_type": "None",
            "frustration_score": 2,
            "accuracy_score": 8,
            "highlights": [],
            "grade_panel": {
                "ai_performance": {"relevancy_score": 8, "accuracy_score": 8},
                "conversation_health": {"resolution": True, "loop_detected": False},
                "user_signals": {"satisfaction_score": 8, "frustration_score": 2},
                "escalation": {"escalation_occurred": False, "escalation_type": "None"},
                "intent": {"intent_code": "policy_inquiry", "intent_label": "Policy Inquiry"},
            },
            "transcript": [
                {
                    "role": "user",
                    "content": "Need help with my policy.",
                    "created_at": "2026-03-11T11:00:00",
                }
            ],
            "recent_history": [],
        }
    )

    assert response.detail.grade_panel.ai_performance["relevancy_score"] == 8
    assert response.detail.transcript[0].role == "user"


def test_monitoring_error_response_rejects_blank_detail_items() -> None:
    with pytest.raises(ValidationError):
        MonitoringErrorResponse(
            code="invalid_sort",
            message="Sort is invalid.",
            details=["   "],
        )


def test_grading_dashboard_window_query_defaults_to_previous_gst_window() -> None:
    query = GradingDashboardWindowQuery()

    assert query.start_date is not None
    assert query.end_date is not None
    assert (query.end_date - query.start_date).days == 6


def test_grading_dashboard_daily_timeline_query_defaults_to_previous_gst_day_and_limit() -> None:
    query = GradingDashboardDailyTimelineQuery()

    assert query.target_date is not None
    assert query.worst_performers_limit == 10


def test_grading_dashboard_error_response_rejects_blank_detail_items() -> None:
    with pytest.raises(ValidationError):
        GradingDashboardErrorResponse(
            code="invalid_date_window",
            message="Dashboard request is invalid.",
            details=["   "],
        )


def test_grading_dashboard_agent_pulse_response_accepts_canonical_payload() -> None:
    response = GradingDashboardAgentPulseResponse(
        date_window={"start_date": "2026-03-05", "end_date": "2026-03-11"},
        total_graded_customer_days=12,
        overall_composite_score=8.1,
        dimension_averages={
            "relevancy": 8.2,
            "accuracy": 7.9,
            "completeness": 8.0,
            "clarity": 8.3,
            "tone": 8.4,
        },
        health={
            "resolution_rate_pct": 83.3,
            "avg_repetition_score": 7.2,
            "loop_detected_rate_pct": 8.3,
        },
        escalation_breakdown=[
            {"escalation_type": "Natural", "count": 1, "share_pct": 8.3},
            {"escalation_type": "Failure", "count": 1, "share_pct": 8.3},
            {"escalation_type": "None", "count": 10, "share_pct": 83.4},
        ],
        user_signals={
            "avg_satisfaction_score": 7.8,
            "avg_frustration_score": 2.2,
            "user_relevancy_rate_pct": 91.7,
        },
        trend_points=[
            {
                "date": "2026-03-11",
                "overall_composite_score": 8.0,
                "satisfaction_score": 7.9,
                "frustration_score": 2.1,
            }
        ],
        top_intents=[
            {
                "intent_code": "policy_inquiry",
                "intent_label": "Policy Inquiry",
                "intent_category": "Policy Related",
                "count": 5,
            }
        ],
        attention_signals=[
            {
                "code": "failure_escalation_rate_pct",
                "severity": "warning",
                "label": "Failure escalations rising",
                "metric_key": "escalation_failure_rate_pct",
                "value": 8.3,
                "message": "Failure escalations are above the early-warning threshold.",
            }
        ],
        freshness={
            "latest_successful_run_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            "latest_successful_window_end_date": "2026-03-11",
            "latest_successful_run_finished_at": "2026-03-12T10:00:00",
        },
    )

    assert response.dimension_averages.relevancy == 8.2
    assert response.top_intents[0].intent_code == "policy_inquiry"


def test_grading_dashboard_correlations_response_accepts_canonical_payload() -> None:
    response = GradingDashboardCorrelationsResponse(
        date_window={"start_date": "2026-03-05", "end_date": "2026-03-11"},
        total_graded_customer_days=12,
        heatmap_cells=[
            {
                "dimension_key": "relevancy",
                "dimension_label": "Relevancy",
                "score_bucket": "1-4",
                "conversation_count": 2,
                "avg_satisfaction_score": 4.5,
            }
        ],
        failure_funnel=[
            {
                "step_key": "total_graded_customer_days",
                "label": "Total graded customer-days",
                "count": 12,
            },
            {
                "step_key": "loop_detected",
                "label": "Loop detected",
                "count": 2,
            },
        ],
        frustration_histogram=[
            {
                "bucket_label": "1-2",
                "min_score": 1,
                "max_score": 2,
                "count": 4,
                "share_pct": 33.3,
            }
        ],
        story_cards=[
            {
                "code": "failure_escalation_rate_pct",
                "severity": "critical",
                "title": "Failure escalations are elevated",
                "metric_key": "escalation_failure_rate_pct",
                "metric_value": 12.5,
                "explanation": "Failure escalations exceeded the critical threshold.",
            }
        ],
        freshness={
            "latest_successful_run_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            "latest_successful_window_end_date": "2026-03-11",
            "latest_successful_run_finished_at": "2026-03-12T10:00:00",
        },
    )

    assert response.heatmap_cells[0].score_bucket == "1-4"
    assert response.story_cards[0].severity.value == "critical"


def test_grading_dashboard_daily_timeline_response_accepts_canonical_payload() -> None:
    response = GradingDashboardDailyTimelineResponse(
        target_date="2026-03-11",
        hourly_buckets=[
            {"hour": 0, "conversation_volume": 0, "resolution_rate_pct": 0.0},
            {"hour": 10, "conversation_volume": 3, "resolution_rate_pct": 100.0},
        ],
        best_hour={"hour": 10, "conversation_volume": 3, "resolution_rate_pct": 100.0},
        worst_hour={"hour": 0, "conversation_volume": 0, "resolution_rate_pct": 0.0},
        scatter_points=[
            {
                "grade_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
                "conversation_key": "phone:+971500000001",
                "satisfaction_score": 8,
                "frustration_score": 2,
                "resolution": True,
                "loop_detected": False,
            }
        ],
        worst_performers=[
            {
                "grade_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
                "conversation_key": "phone:+971500000001",
                "contact_label": "Jane Doe",
                "relevancy_score": 4,
                "accuracy_score": 5,
                "completeness_score": 4,
                "clarity_score": 5,
                "tone_score": 6,
                "satisfaction_score": 3,
                "frustration_score": 8,
                "resolution": False,
                "escalation_type": "Failure",
                "intent_code": "policy_inquiry",
                "intent_label": "Policy Inquiry",
                "intent_category": "Policy Related",
            }
        ],
        freshness={
            "latest_successful_run_id": "df35ea32-c0b2-46e4-954e-7707b9d3a62b",
            "latest_successful_window_end_date": "2026-03-11",
            "latest_successful_run_finished_at": "2026-03-12T10:00:00",
        },
    )

    assert response.best_hour is not None
    assert response.worst_performers[0].intent_label == "Policy Inquiry"
