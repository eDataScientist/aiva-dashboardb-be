from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Mapping, Protocol, Sequence

from pydantic import ValidationError

from app.core.constants import INTENT_CODE_TO_LABEL, INTENT_LABEL_TO_CODE
from app.schemas.grading import (
    GradingOutput,
    GradingParseError,
    GradingParseErrorCode,
)
from app.schemas.grading_prompts import (
    AIPerformancePromptOutput,
    ConversationHealthPromptOutput,
    EscalationPromptOutput,
    IntentPromptOutput,
    PromptDomain,
    PromptDomainOutput,
    PromptPackPartialOutputs,
    UserSignalsPromptOutput,
)
from app.services.grading_prompt import PromptBundle


class GradingParseFailure(RuntimeError):
    """Raised when provider output cannot be validated against the grading schema."""

    def __init__(self, error: GradingParseError):
        super().__init__(error.message)
        self.error = error


@dataclass(frozen=True, slots=True)
class ParsedGradingResult:
    output: GradingOutput


@dataclass(frozen=True, slots=True)
class ParsedPromptDomainResult:
    prompt_key: PromptDomain
    raw_output: str
    output: PromptDomainOutput


@dataclass(frozen=True, slots=True)
class ParsedPromptExecutionResult:
    domain_results: tuple[ParsedPromptDomainResult, ...]
    partial_outputs: PromptPackPartialOutputs
    output: GradingOutput


class GradingParser(Protocol):
    def __call__(self, raw_output: str) -> ParsedGradingResult: ...


class PromptExecutionParser(Protocol):
    def __call__(
        self,
        raw_outputs: Mapping[PromptDomain | str, str]
        | Sequence[tuple[PromptBundle, str]],
    ) -> ParsedPromptExecutionResult: ...


def parse_grading_output(raw_output: str) -> ParsedGradingResult:
    normalized_raw_output = raw_output.strip()
    payload = _load_json_object(
        normalized_raw_output,
        invalid_json_message="Provider output is not valid JSON.",
        invalid_root_message="Provider output must decode to a JSON object.",
    )

    try:
        validated_output = GradingOutput.model_validate(payload)
    except ValidationError as exc:
        raise GradingParseFailure(
            _build_validation_parse_error(exc, normalized_raw_output)
        ) from exc

    return ParsedGradingResult(output=validated_output)


def parse_prompt_domain_output(
    prompt_key: PromptDomain | str,
    raw_output: str,
) -> ParsedPromptDomainResult:
    resolved_prompt_key = PromptDomain(prompt_key)
    normalized_raw_output = raw_output.strip()
    payload = _load_json_object(
        normalized_raw_output,
        invalid_json_message=(
            f"Prompt-domain output for '{resolved_prompt_key.value}' is not valid JSON."
        ),
        invalid_root_message=(
            f"Prompt-domain output for '{resolved_prompt_key.value}' must decode to a JSON object."
        ),
    )

    model_type = _PROMPT_DOMAIN_OUTPUT_MODELS[resolved_prompt_key]
    try:
        validated_output = model_type.model_validate(payload)
    except ValidationError as exc:
        raise GradingParseFailure(
            _build_validation_parse_error(
                exc,
                normalized_raw_output,
                field_prefix=resolved_prompt_key.value,
            )
        ) from exc

    return ParsedPromptDomainResult(
        prompt_key=resolved_prompt_key,
        raw_output=normalized_raw_output,
        output=validated_output,
    )


def parse_prompt_execution_results(
    raw_outputs: Mapping[PromptDomain | str, str]
    | Sequence[tuple[PromptBundle, str]],
) -> ParsedPromptExecutionResult:
    prompt_domain_outputs = _normalize_prompt_domain_outputs(raw_outputs)
    missing_prompt_domains = [
        prompt_domain.value
        for prompt_domain in PromptDomain
        if prompt_domain not in prompt_domain_outputs
    ]
    if missing_prompt_domains:
        raise GradingParseFailure(
            GradingParseError(
                code=GradingParseErrorCode.MISSING_REQUIRED_FIELD,
                message="Prompt-pack execution is missing one or more required prompt-domain outputs.",
                details=[
                    f"{prompt_domain}: Missing prompt-domain output."
                    for prompt_domain in missing_prompt_domains
                ],
            )
        )

    domain_results = tuple(
        parse_prompt_domain_output(
            prompt_key=prompt_domain,
            raw_output=prompt_domain_outputs[prompt_domain],
        )
        for prompt_domain in PromptDomain
    )
    partial_outputs = PromptPackPartialOutputs.model_validate(
        {
            domain_result.prompt_key.value: domain_result.output.model_dump()
            for domain_result in domain_results
        }
    )
    merged_output = merge_prompt_pack_outputs(partial_outputs)
    return ParsedPromptExecutionResult(
        domain_results=domain_results,
        partial_outputs=partial_outputs,
        output=merged_output,
    )


def merge_prompt_pack_outputs(partial_outputs: PromptPackPartialOutputs) -> GradingOutput:
    intent_code, intent_label = _normalize_intent_label(partial_outputs.intent.intent_label)
    payload = {
        **partial_outputs.ai_performance.model_dump(),
        **partial_outputs.conversation_health.model_dump(),
        **partial_outputs.user_signals.model_dump(),
        **partial_outputs.escalation.model_dump(),
        "intent_code": intent_code,
        "intent_label": intent_label,
        "intent_reasoning": partial_outputs.intent.intent_reasoning,
    }
    serialized_payload = json.dumps(payload, ensure_ascii=True, sort_keys=True)

    try:
        return GradingOutput.model_validate(payload)
    except ValidationError as exc:
        raise GradingParseFailure(
            _build_validation_parse_error(exc, serialized_payload)
        ) from exc


def _normalize_prompt_domain_outputs(
    raw_outputs: Mapping[PromptDomain | str, str]
    | Sequence[tuple[PromptBundle, str]],
) -> dict[PromptDomain, str]:
    if isinstance(raw_outputs, Mapping):
        normalized_mapping_outputs: dict[PromptDomain, str] = {}
        for prompt_key, raw_output in raw_outputs.items():
            try:
                prompt_domain = PromptDomain(prompt_key)
            except ValueError as exc:
                raise GradingParseFailure(
                    GradingParseError(
                        code=GradingParseErrorCode.FIELD_VALIDATION_ERROR,
                        message="Prompt output mapping contains an unsupported prompt domain.",
                        details=[f"prompt_key: {prompt_key}"],
                    )
                ) from exc
            normalized_mapping_outputs[prompt_domain] = raw_output
        return normalized_mapping_outputs

    normalized_outputs: dict[PromptDomain, str] = {}
    for prompt_bundle, raw_output in raw_outputs:
        if prompt_bundle.prompt_domain is not None:
            prompt_domain = prompt_bundle.prompt_domain
        else:
            try:
                prompt_domain = PromptDomain(prompt_bundle.prompt_key)
            except ValueError as exc:
                raise GradingParseFailure(
                    GradingParseError(
                        code=GradingParseErrorCode.FIELD_VALIDATION_ERROR,
                        message="Prompt bundle does not identify a supported prompt domain.",
                        details=[f"prompt_key: {prompt_bundle.prompt_key}"],
                    )
                ) from exc
        if prompt_domain in normalized_outputs:
            raise GradingParseFailure(
                GradingParseError(
                    code=GradingParseErrorCode.FIELD_VALIDATION_ERROR,
                    message="Prompt-pack execution contains duplicate prompt-domain outputs.",
                    details=[f"{prompt_domain.value}: duplicate prompt-domain output."],
                )
            )
        normalized_outputs[prompt_domain] = raw_output
    return normalized_outputs


def _load_json_object(
    raw_output: str,
    *,
    invalid_json_message: str,
    invalid_root_message: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(raw_output)
    except JSONDecodeError as exc:
        raise GradingParseFailure(
            GradingParseError(
                code=GradingParseErrorCode.INVALID_JSON,
                message=invalid_json_message,
                raw_output=raw_output or None,
                details=[str(exc)],
            )
        ) from exc

    if not isinstance(payload, dict):
        raise GradingParseFailure(
            GradingParseError(
                code=GradingParseErrorCode.INVALID_ROOT,
                message=invalid_root_message,
                raw_output=raw_output or None,
            )
        )
    return payload


def _normalize_intent_label(intent_label: str) -> tuple[str, str]:
    normalized_label = " ".join(intent_label.split()).casefold()
    intent_code = _NORMALIZED_INTENT_LABEL_TO_CODE.get(normalized_label)
    if intent_code is None:
        raise GradingParseFailure(
            GradingParseError(
                code=GradingParseErrorCode.INTENT_LABEL_MISMATCH,
                message="Prompt-pack intent_label does not map to the canonical taxonomy.",
                raw_output=intent_label.strip() or None,
                details=[f"intent.intent_label: Unsupported label '{intent_label.strip()}'."],
            )
        )
    return intent_code, INTENT_CODE_TO_LABEL[intent_code]


def _build_validation_parse_error(
    exc: ValidationError,
    raw_output: str,
    *,
    field_prefix: str | None = None,
) -> GradingParseError:
    details: list[str] = []
    has_missing_required_field = False
    has_intent_label_mismatch = False

    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ()))
        if field_prefix:
            location = f"{field_prefix}.{location}" if location else field_prefix
        message = error.get("msg", "Validation error.")
        error_type = error.get("type", "")

        if error_type == "missing":
            has_missing_required_field = True
        if "intent_label must match canonical label" in message:
            has_intent_label_mismatch = True

        if location:
            details.append(f"{location}: {message}")
        else:
            details.append(message)

    if has_intent_label_mismatch:
        code = GradingParseErrorCode.INTENT_LABEL_MISMATCH
        message = "intent_code and intent_label do not match the canonical taxonomy."
    elif has_missing_required_field:
        code = GradingParseErrorCode.MISSING_REQUIRED_FIELD
        message = "Provider output is missing one or more required grading fields."
    else:
        code = GradingParseErrorCode.FIELD_VALIDATION_ERROR
        message = "Provider output failed grading field validation."

    return GradingParseError(
        code=code,
        message=message,
        raw_output=raw_output,
        details=details,
    )


_PROMPT_DOMAIN_OUTPUT_MODELS: dict[PromptDomain, type[PromptDomainOutput]] = {
    PromptDomain.AI_PERFORMANCE: AIPerformancePromptOutput,
    PromptDomain.CONVERSATION_HEALTH: ConversationHealthPromptOutput,
    PromptDomain.USER_SIGNALS: UserSignalsPromptOutput,
    PromptDomain.ESCALATION: EscalationPromptOutput,
    PromptDomain.INTENT: IntentPromptOutput,
}

_NORMALIZED_INTENT_LABEL_TO_CODE: dict[str, str] = {
    " ".join(label.split()).casefold(): code
    for label, code in INTENT_LABEL_TO_CODE.items()
}
