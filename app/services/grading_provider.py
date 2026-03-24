from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

import openai

from app.core.config import Settings, get_settings
from app.core.constants import (
    GRADING_PROVIDER_MOCK,
    GRADING_PROVIDER_OPENAI_COMPATIBLE,
)
from app.schemas.grading_prompts import PromptDomain
from app.services.grading_prompt import PromptBundle


class GradingProviderError(RuntimeError):
    """Raised when the grading provider transport/runtime layer fails."""


@dataclass(frozen=True, slots=True)
class GradingProviderRequest:
    prompt: PromptBundle
    model: str
    timeout_seconds: int
    max_retries: int


class GradingProvider(Protocol):
    async def __call__(self, request: GradingProviderRequest) -> str: ...


class MockGradingTransport(Protocol):
    async def __call__(self, request: GradingProviderRequest) -> str: ...


class OpenAICompatibleTransport(Protocol):
    async def __call__(
        self,
        request: GradingProviderRequest,
        settings: Settings,
    ) -> str: ...


def build_grading_provider(
    *,
    settings: Settings | None = None,
    mock_transport: MockGradingTransport | None = None,
    openai_transport: OpenAICompatibleTransport | None = None,
) -> GradingProvider:
    resolved_settings = settings or get_settings()

    if resolved_settings.grading_provider == GRADING_PROVIDER_MOCK:
        transport = mock_transport or _default_mock_transport
        return _build_retrying_provider(
            lambda request: transport(request),
        )

    if resolved_settings.grading_provider == GRADING_PROVIDER_OPENAI_COMPATIBLE:
        transport = openai_transport or _default_openai_compatible_transport
        return _build_retrying_provider(
            lambda request: transport(request, resolved_settings),
        )

    raise GradingProviderError(
        f"Unsupported grading provider '{resolved_settings.grading_provider}'."
    )


def _build_retrying_provider(
    invoke: Callable[[GradingProviderRequest], Awaitable[str]],
) -> GradingProvider:
    async def provider(request: GradingProviderRequest) -> str:
        attempts = max(request.max_retries, 0) + 1
        last_error: GradingProviderError | None = None

        for _ in range(attempts):
            try:
                raw_output = await invoke(request)
            except GradingProviderError as exc:
                last_error = exc
                continue

            normalized_output = raw_output.strip()
            if not normalized_output:
                raise GradingProviderError(
                    "Grading provider returned an empty completion payload."
                )
            return normalized_output

        if last_error is not None:
            raise last_error
        raise GradingProviderError("Grading provider failed without an error payload.")

    return provider


async def _default_mock_transport(request: GradingProviderRequest) -> str:
    mock_response = _serialize_mock_response(
        request.prompt.metadata.get("mock_response")
    )
    if mock_response is not None:
        return mock_response

    mock_responses = request.prompt.metadata.get("mock_responses")
    if isinstance(mock_responses, dict):
        keyed_response = _serialize_mock_response(
            mock_responses.get(request.prompt.prompt_key)
        )
        if keyed_response is not None:
            return keyed_response

    return json.dumps(
        _build_default_mock_payload(request),
        ensure_ascii=True,
    )


def _build_default_mock_payload(request: GradingProviderRequest) -> dict[str, object]:
    prompt_key = request.prompt.prompt_key
    conversation_identity = request.prompt.metadata.get(
        "conversation_identity",
        "unknown-identity",
    )
    grade_date = request.prompt.metadata.get("grade_date", "unknown-date")
    reasoning_context = (
        "Deterministic mock grading output "
        f"for {conversation_identity} on {grade_date} "
        f"via {prompt_key} ({request.prompt.prompt_version})."
    )

    full_payload = {
        "relevancy_score": 8,
        "relevancy_reasoning": reasoning_context,
        "accuracy_score": 8,
        "accuracy_reasoning": reasoning_context,
        "completeness_score": 7,
        "completeness_reasoning": reasoning_context,
        "clarity_score": 8,
        "clarity_reasoning": reasoning_context,
        "tone_score": 8,
        "tone_reasoning": reasoning_context,
        "resolution": True,
        "resolution_reasoning": reasoning_context,
        "repetition_score": 8,
        "repetition_reasoning": reasoning_context,
        "loop_detected": False,
        "loop_detected_reasoning": reasoning_context,
        "satisfaction_score": 7,
        "satisfaction_reasoning": reasoning_context,
        "frustration_score": 2,
        "frustration_reasoning": reasoning_context,
        "user_relevancy": True,
        "user_relevancy_reasoning": reasoning_context,
        "escalation_occurred": False,
        "escalation_occurred_reasoning": reasoning_context,
        "escalation_type": "None",
        "escalation_type_reasoning": reasoning_context,
        "intent_code": "general_inquiry",
        "intent_label": "General Inquiry",
        "intent_reasoning": reasoning_context,
    }

    if request.prompt.prompt_domain is None:
        return full_payload

    return _PROMPT_DOMAIN_DEFAULT_OUTPUT_BUILDERS[request.prompt.prompt_domain](
        full_payload
    )


def _serialize_mock_response(response: object) -> str | None:
    if isinstance(response, str):
        normalized_response = response.strip()
        if normalized_response:
            return normalized_response
        return None
    if isinstance(response, dict):
        return json.dumps(response, ensure_ascii=True)
    return None


async def _default_openai_compatible_transport(
    request: GradingProviderRequest,
    settings: Settings,
) -> str:
    client_kwargs: dict[str, object] = {
        "api_key": settings.grading_api_key,
        "timeout": float(request.timeout_seconds),
    }
    if settings.grading_base_url:
        client_kwargs["base_url"] = settings.grading_base_url

    messages: list[dict[str, str]] = []
    if request.prompt.system_prompt is not None:
        messages.append(
            {
                "role": "system",
                "content": request.prompt.system_prompt,
            }
        )
    messages.append(
        {
            "role": "user",
            "content": request.prompt.user_prompt,
        }
    )

    try:
        async with openai.AsyncOpenAI(**client_kwargs) as client:
            completion = await client.chat.completions.create(
                model=request.model,
                messages=messages,
                response_format={"type": "json_object"},
            )
    except openai.APITimeoutError as exc:
        raise GradingProviderError(
            f"Grading provider timed out after {request.timeout_seconds} seconds."
        ) from exc
    except openai.APIStatusError as exc:
        raise GradingProviderError(
            f"Grading provider returned HTTP {exc.status_code}."
        ) from exc
    except openai.APIConnectionError as exc:
        raise GradingProviderError("Grading provider request failed.") from exc

    try:
        content = completion.choices[0].message.content
    except (IndexError, AttributeError) as exc:
        raise GradingProviderError(
            "Grading provider returned an unexpected response payload."
        ) from exc

    if not isinstance(content, str):
        raise GradingProviderError(
            "Grading provider returned a non-string completion payload."
        )
    return content


def _build_ai_performance_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    return {
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
    }


def _build_conversation_health_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "resolution": payload["resolution"],
        "resolution_reasoning": payload["resolution_reasoning"],
        "repetition_score": payload["repetition_score"],
        "repetition_reasoning": payload["repetition_reasoning"],
        "loop_detected": payload["loop_detected"],
        "loop_detected_reasoning": payload["loop_detected_reasoning"],
    }


def _build_user_signals_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "satisfaction_score": payload["satisfaction_score"],
        "satisfaction_reasoning": payload["satisfaction_reasoning"],
        "frustration_score": payload["frustration_score"],
        "frustration_reasoning": payload["frustration_reasoning"],
        "user_relevancy": payload["user_relevancy"],
        "user_relevancy_reasoning": payload["user_relevancy_reasoning"],
    }


def _build_escalation_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "escalation_occurred": payload["escalation_occurred"],
        "escalation_occurred_reasoning": payload["escalation_occurred_reasoning"],
        "escalation_type": payload["escalation_type"],
        "escalation_type_reasoning": payload["escalation_type_reasoning"],
    }


def _build_intent_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "intent_label": payload["intent_label"],
        "intent_reasoning": payload["intent_reasoning"],
    }


_PROMPT_DOMAIN_DEFAULT_OUTPUT_BUILDERS: dict[
    PromptDomain, Callable[[dict[str, object]], dict[str, object]]
] = {
    PromptDomain.AI_PERFORMANCE: _build_ai_performance_payload,
    PromptDomain.CONVERSATION_HEALTH: _build_conversation_health_payload,
    PromptDomain.USER_SIGNALS: _build_user_signals_payload,
    PromptDomain.ESCALATION: _build_escalation_payload,
    PromptDomain.INTENT: _build_intent_payload,
}
