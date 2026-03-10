from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.grading import GradingOutput, GradingParseError
from app.schemas.grading_prompts import (
    PromptDomain,
    PromptPackManifest,
    PromptPackPartialOutputs,
    PromptTemplateSpec,
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
