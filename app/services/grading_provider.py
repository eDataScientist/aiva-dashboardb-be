from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.constants import (
    GRADING_PROVIDER_MOCK,
    GRADING_PROVIDER_OPENAI_COMPATIBLE,
)
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
    mock_response = request.prompt.metadata.get("mock_response")
    if isinstance(mock_response, str) and mock_response.strip():
        return mock_response

    return json.dumps(
        _build_default_mock_payload(request),
        ensure_ascii=True,
    )


def _build_default_mock_payload(request: GradingProviderRequest) -> dict[str, object]:
    conversation_identity = request.prompt.metadata.get(
        "conversation_identity",
        "unknown-identity",
    )
    grade_date = request.prompt.metadata.get("grade_date", "unknown-date")
    reasoning_context = (
        f"Deterministic mock grading output for {conversation_identity} on {grade_date}."
    )

    return {
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


async def _default_openai_compatible_transport(
    request: GradingProviderRequest,
    settings: Settings,
) -> str:
    base_url = (settings.grading_base_url or "https://api.openai.com/v1").rstrip("/")
    timeout = httpx.Timeout(request.timeout_seconds)
    messages = []
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
    payload = {
        "model": request.model,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {settings.grading_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise GradingProviderError(
            f"Grading provider timed out after {request.timeout_seconds} seconds."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise GradingProviderError(
            f"Grading provider returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise GradingProviderError("Grading provider request failed.") from exc

    try:
        response_payload = response.json()
        content = response_payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise GradingProviderError(
            "Grading provider returned an unexpected response payload."
        ) from exc

    if not isinstance(content, str):
        raise GradingProviderError(
            "Grading provider returned a non-string completion payload."
        )
    return content
