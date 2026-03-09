from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.grading import GradingOutput, GradingParseError


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
