from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.core.config import Settings
from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION
from app.models.enums import IdentityType
from app.schemas.grading import GradingParseErrorCode
from app.schemas.grading_prompts import PromptDomain
from app.services.grading_parser import (
    GradingParseFailure,
    parse_grading_output,
    parse_prompt_domain_output,
    parse_prompt_execution_results,
)
from app.services.grading_extraction import (
    CustomerDayCandidate,
    CustomerDayTranscript,
    TranscriptMessage,
)
from app.services.grading_prompt import (
    PromptBundle,
    build_grading_prompt,
    build_prompt_execution_plan,
)
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


def _provider_request(
    mock_response: str | None = None,
    *,
    model: str = GRADING_DEFAULT_MODEL,
) -> GradingProviderRequest:
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
        model=model,
        timeout_seconds=5,
        max_retries=2,
    )


def _partial_provider_payloads() -> dict[str, dict[str, object]]:
    payload = _valid_provider_payload()
    return {
        "ai_performance": {
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
        "conversation_health": {
            "resolution": payload["resolution"],
            "resolution_reasoning": payload["resolution_reasoning"],
            "repetition_score": payload["repetition_score"],
            "repetition_reasoning": payload["repetition_reasoning"],
            "loop_detected": payload["loop_detected"],
            "loop_detected_reasoning": payload["loop_detected_reasoning"],
        },
        "user_signals": {
            "satisfaction_score": payload["satisfaction_score"],
            "satisfaction_reasoning": payload["satisfaction_reasoning"],
            "frustration_score": payload["frustration_score"],
            "frustration_reasoning": payload["frustration_reasoning"],
            "user_relevancy": payload["user_relevancy"],
            "user_relevancy_reasoning": payload["user_relevancy_reasoning"],
        },
        "escalation": {
            "escalation_occurred": payload["escalation_occurred"],
            "escalation_occurred_reasoning": payload["escalation_occurred_reasoning"],
            "escalation_type": payload["escalation_type"],
            "escalation_type_reasoning": payload["escalation_type_reasoning"],
        },
        "intent": {
            "intent_label": payload["intent_label"],
            "intent_reasoning": payload["intent_reasoning"],
        },
    }


def _settings(
    *,
    grading_provider: str,
    grading_api_key: str | None = None,
    openrouter_api_key: str | None = None,
    grading_base_url: str | None = None,
    grading_model: str | None = None,
) -> Settings:
    kwargs: dict[str, object] = {
        "database_url": "sqlite:///tests.db",
        "auth_jwt_secret": "x" * 32,
        "auth_jwt_algorithm": "HS256",
        "auth_access_token_expire_minutes": 60,
        "grading_provider": grading_provider,
        "grading_model": grading_model or GRADING_DEFAULT_MODEL,
        "grading_prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
    }
    if grading_api_key is not None:
        kwargs["grading_api_key"] = grading_api_key
    if openrouter_api_key is not None:
        kwargs["openrouter_api_key"] = openrouter_api_key
    if grading_base_url is not None:
        kwargs["grading_base_url"] = grading_base_url
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


def test_parse_prompt_domain_output_accepts_bounded_domain_payload() -> None:
    payload = _partial_provider_payloads()

    result = parse_prompt_domain_output(
        PromptDomain.AI_PERFORMANCE,
        json.dumps(payload["ai_performance"]),
    )

    assert result.prompt_key is PromptDomain.AI_PERFORMANCE
    assert result.output.relevancy_score == 8


def test_parse_prompt_execution_results_merges_partial_outputs() -> None:
    payload = _partial_provider_payloads()
    payload["intent"]["intent_label"] = "  policy inquiry  "

    result = parse_prompt_execution_results(
        {
            prompt_key: json.dumps(prompt_payload)
            for prompt_key, prompt_payload in payload.items()
        }
    )

    assert [domain_result.prompt_key.value for domain_result in result.domain_results] == [
        "ai_performance",
        "conversation_health",
        "user_signals",
        "escalation",
        "intent",
    ]
    assert result.partial_outputs.intent.intent_label == "  policy inquiry  "
    assert result.output.intent_code == "policy_inquiry"
    assert result.output.intent_label == "Policy Inquiry"
    assert result.output.repetition_score == 8


def test_merge_prompt_pack_outputs_rejects_unknown_intent_label() -> None:
    payload = _partial_provider_payloads()
    payload["intent"]["intent_label"] = "Unmapped label"

    with pytest.raises(GradingParseFailure) as exc_info:
        parse_prompt_execution_results(
            {
                prompt_key: json.dumps(prompt_payload)
                for prompt_key, prompt_payload in payload.items()
            }
        )

    assert exc_info.value.error.code == GradingParseErrorCode.INTENT_LABEL_MISMATCH


def test_parse_prompt_execution_results_rejects_missing_prompt_domain() -> None:
    payload = _partial_provider_payloads()
    payload.pop("intent")

    with pytest.raises(GradingParseFailure) as exc_info:
        parse_prompt_execution_results(
            {
                prompt_key: json.dumps(prompt_payload)
                for prompt_key, prompt_payload in payload.items()
            }
        )

    assert exc_info.value.error.code == GradingParseErrorCode.MISSING_REQUIRED_FIELD
    assert "intent: Missing prompt-domain output." in exc_info.value.error.details


def test_parse_prompt_execution_results_rejects_unsupported_mapping_key() -> None:
    with pytest.raises(GradingParseFailure) as exc_info:
        parse_prompt_execution_results({"unsupported": "{}"})

    assert exc_info.value.error.code == GradingParseErrorCode.FIELD_VALIDATION_ERROR
    assert exc_info.value.error.details == ["prompt_key: unsupported"]


def test_parse_prompt_execution_results_prefixes_domain_validation_errors() -> None:
    payload = _partial_provider_payloads()
    payload["escalation"].pop("escalation_type_reasoning")

    with pytest.raises(GradingParseFailure) as exc_info:
        parse_prompt_execution_results(
            {
                prompt_key: json.dumps(prompt_payload)
                for prompt_key, prompt_payload in payload.items()
            }
        )

    assert exc_info.value.error.code == GradingParseErrorCode.MISSING_REQUIRED_FIELD
    assert "escalation.escalation_type_reasoning" in exc_info.value.error.details[0]


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
async def test_build_grading_provider_supports_prompt_pack_execution_with_default_mock_path() -> None:
    provider = build_grading_provider(settings=_settings(grading_provider="mock"))
    plan = build_prompt_execution_plan(_transcript())

    raw_outputs: list[tuple[PromptBundle, str]] = []
    for bundle in plan.bundles:
        raw_outputs.append(
            (
                bundle,
                await provider(
                    GradingProviderRequest(
                        prompt=bundle,
                        model=GRADING_DEFAULT_MODEL,
                        timeout_seconds=5,
                        max_retries=0,
                    )
                ),
            )
        )
    parsed = parse_prompt_execution_results(tuple(raw_outputs))

    assert len(raw_outputs) == 5
    assert [bundle.prompt_key for bundle, _ in raw_outputs] == [
        prompt_domain.value for prompt_domain in PromptDomain
    ]
    assert parsed.output.intent_code == "general_inquiry"
    assert parsed.output.intent_label == "General Inquiry"
    assert parsed.output.relevancy_score == 8


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


@pytest.mark.asyncio
async def test_build_grading_provider_uses_openrouter_api_key_alias() -> None:
    captured: dict[str, object] = {}

    async def fake_openai_transport(
        request: GradingProviderRequest,
        settings: Settings,
    ) -> str:
        captured["model"] = request.model
        captured["provider"] = settings.grading_provider
        captured["api_key"] = settings.grading_api_key
        captured["base_url"] = settings.grading_base_url
        return '{"ok": true}'

    provider = build_grading_provider(
        settings=_settings(
            grading_provider="openai_compatible",
            openrouter_api_key="openrouter-key",
            grading_base_url="https://openrouter.ai/api/v1",
            grading_model="minimax/minimax-m2.5",
        ),
        openai_transport=fake_openai_transport,
    )

    raw_output = await provider(
        _provider_request(model="minimax/minimax-m2.5")
    )

    assert raw_output == '{"ok": true}'
    assert captured == {
        "model": "minimax/minimax-m2.5",
        "provider": "openai_compatible",
        "api_key": "openrouter-key",
        "base_url": "https://openrouter.ai/api/v1",
    }


@pytest.mark.asyncio
async def test_build_grading_provider_passes_prompt_pack_metadata_to_openai_transport() -> None:
    captured_requests: list[dict[str, object]] = []
    plan = build_prompt_execution_plan(_transcript())

    async def fake_openai_transport(
        request: GradingProviderRequest,
        settings: Settings,
    ) -> str:
        captured_requests.append(
            {
                "prompt_key": request.prompt.prompt_key,
                "prompt_version": request.prompt.prompt_version,
                "template_file": request.prompt.template_file,
                "sequence": request.prompt.metadata["prompt_sequence"],
                "provider": settings.grading_provider,
            }
        )
        return '{"ok": true}'

    provider = build_grading_provider(
        settings=_settings(
            grading_provider="openai_compatible",
            grading_api_key="api-key",
        ),
        openai_transport=fake_openai_transport,
    )

    for bundle in plan.bundles:
        await provider(
            GradingProviderRequest(
                prompt=bundle,
                model=GRADING_DEFAULT_MODEL,
                timeout_seconds=5,
                max_retries=0,
            )
        )

    assert captured_requests == [
        {
            "prompt_key": "ai_performance",
            "prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
            "template_file": "ai_performance_judge.md",
            "sequence": 1,
            "provider": "openai_compatible",
        },
        {
            "prompt_key": "conversation_health",
            "prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
            "template_file": "conversation_health.md",
            "sequence": 2,
            "provider": "openai_compatible",
        },
        {
            "prompt_key": "user_signals",
            "prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
            "template_file": "user-signals.md",
            "sequence": 3,
            "provider": "openai_compatible",
        },
        {
            "prompt_key": "escalation",
            "prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
            "template_file": "escalation.md",
            "sequence": 4,
            "provider": "openai_compatible",
        },
        {
            "prompt_key": "intent",
            "prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
            "template_file": "intent.md",
            "sequence": 5,
            "provider": "openai_compatible",
        },
    ]
