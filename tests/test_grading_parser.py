from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.core.config import Settings
from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION
from app.models.enums import IdentityType
from app.schemas.grading import GradingParseErrorCode
from app.services.grading_parser import GradingParseFailure, parse_grading_output
from app.services.grading_extraction import (
    CustomerDayCandidate,
    CustomerDayTranscript,
    TranscriptMessage,
)
from app.services.grading_prompt import PromptBundle, build_grading_prompt
from app.services.grading_provider import (
    GradingProviderError,
    GradingProviderRequest,
    build_grading_provider,
)


def _valid_provider_payload() -> dict[str, object]:
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


def _provider_request(mock_response: str | None = None) -> GradingProviderRequest:
    metadata: dict[str, object] = {}
    if mock_response is not None:
        metadata["mock_response"] = mock_response

    return GradingProviderRequest(
        prompt=PromptBundle(
            system_prompt="system",
            user_prompt="user",
            prompt_version=GRADING_DEFAULT_PROMPT_VERSION,
            metadata=metadata,
        ),
        model=GRADING_DEFAULT_MODEL,
        timeout_seconds=5,
        max_retries=2,
    )


def _settings(*, grading_provider: str, grading_api_key: str | None = None) -> Settings:
    kwargs: dict[str, object] = {
        "database_url": "sqlite:///tests.db",
        "auth_jwt_secret": "x" * 32,
        "auth_jwt_algorithm": "HS256",
        "auth_access_token_expire_minutes": 60,
        "grading_provider": grading_provider,
        "grading_model": GRADING_DEFAULT_MODEL,
        "grading_prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
    }
    if grading_api_key is not None:
        kwargs["grading_api_key"] = grading_api_key
    return Settings(**kwargs)


def _transcript() -> CustomerDayTranscript:
    return CustomerDayTranscript(
        candidate=CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000001",
            grade_date=date(2026, 3, 8),
        ),
        messages=(
            TranscriptMessage(
                chat_id=101,
                created_at=datetime(2026, 3, 8, 8, 30, tzinfo=timezone.utc),
                direction="inbound",
                channel="whatsapp",
                message_type="text",
                message="I need help with my motor policy renewal.",
                intent="Renewal",
                escalated=False,
                normalized_content="I need help with my motor policy renewal.",
                transcript_line=(
                    "2026-03-08T08:30:00+00:00 | direction=inbound | "
                    "channel=whatsapp | message_type=text | escalated=false | "
                    "intent=Renewal | content=I need help with my motor policy renewal."
                ),
            ),
        ),
        transcript_text=(
            "2026-03-08T08:30:00+00:00 | direction=inbound | channel=whatsapp | "
            "message_type=text | escalated=false | intent=Renewal | "
            "content=I need help with my motor policy renewal."
        ),
    )


def test_parse_grading_output_accepts_valid_payload() -> None:
    result = parse_grading_output(json.dumps(_valid_provider_payload()))

    assert result.output.intent_code == "policy_inquiry"
    assert result.output.resolution is True


def test_parse_grading_output_rejects_invalid_json() -> None:
    with pytest.raises(GradingParseFailure) as exc_info:
        parse_grading_output("{invalid")

    assert exc_info.value.error.code == GradingParseErrorCode.INVALID_JSON


def test_parse_grading_output_rejects_non_object_root() -> None:
    with pytest.raises(GradingParseFailure) as exc_info:
        parse_grading_output('["not", "an", "object"]')

    assert exc_info.value.error.code == GradingParseErrorCode.INVALID_ROOT


def test_parse_grading_output_rejects_missing_required_field() -> None:
    payload = _valid_provider_payload()
    payload.pop("tone_reasoning")

    with pytest.raises(GradingParseFailure) as exc_info:
        parse_grading_output(json.dumps(payload))

    assert exc_info.value.error.code == GradingParseErrorCode.MISSING_REQUIRED_FIELD
    assert "tone_reasoning" in exc_info.value.error.details[0]


def test_parse_grading_output_rejects_intent_label_mismatch() -> None:
    payload = _valid_provider_payload()
    payload["intent_label"] = "Claims Follow-up"

    with pytest.raises(GradingParseFailure) as exc_info:
        parse_grading_output(json.dumps(payload))

    assert exc_info.value.error.code == GradingParseErrorCode.INTENT_LABEL_MISMATCH


@pytest.mark.asyncio
async def test_build_grading_provider_reads_default_mock_response_from_metadata() -> None:
    provider = build_grading_provider(settings=_settings(grading_provider="mock"))

    raw_output = await provider(
        _provider_request(mock_response=json.dumps(_valid_provider_payload()))
    )

    assert raw_output.startswith("{")
    assert "policy_inquiry" in raw_output


@pytest.mark.asyncio
async def test_build_grading_provider_supports_real_prompt_builder_output_with_default_mock_path() -> None:
    provider = build_grading_provider(settings=_settings(grading_provider="mock"))

    raw_output = await provider(
        GradingProviderRequest(
            prompt=build_grading_prompt(_transcript()),
            model=GRADING_DEFAULT_MODEL,
            timeout_seconds=5,
            max_retries=0,
        )
    )
    parsed = parse_grading_output(raw_output)

    assert parsed.output.intent_code == "general_inquiry"
    assert parsed.output.intent_label == "General Inquiry"
    assert "+971500000001" in parsed.output.intent_reasoning


@pytest.mark.asyncio
async def test_build_grading_provider_retries_mock_transport_failures() -> None:
    attempts = {"count": 0}

    async def flaky_transport(request: GradingProviderRequest) -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise GradingProviderError("timed out")
        return request.prompt.user_prompt

    provider = build_grading_provider(
        settings=_settings(grading_provider="mock"),
        mock_transport=flaky_transport,
    )

    raw_output = await provider(_provider_request())

    assert raw_output == "user"
    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_build_grading_provider_surfaces_openai_transport_results() -> None:
    captured: dict[str, object] = {}

    async def fake_openai_transport(
        request: GradingProviderRequest,
        settings: Settings,
    ) -> str:
        captured["model"] = request.model
        captured["provider"] = settings.grading_provider
        captured["api_key"] = settings.grading_api_key
        return '{"ok": true}'

    provider = build_grading_provider(
        settings=_settings(
            grading_provider="openai_compatible",
            grading_api_key="api-key",
        ),
        openai_transport=fake_openai_transport,
    )

    raw_output = await provider(_provider_request())

    assert raw_output == '{"ok": true}'
    assert captured == {
        "model": GRADING_DEFAULT_MODEL,
        "provider": "openai_compatible",
        "api_key": "api-key",
    }
