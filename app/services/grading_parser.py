from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Protocol

from pydantic import ValidationError

from app.schemas.grading import (
    GradingOutput,
    GradingParseError,
    GradingParseErrorCode,
)


class GradingParseFailure(RuntimeError):
    """Raised when provider output cannot be validated against the grading schema."""

    def __init__(self, error: GradingParseError):
        super().__init__(error.message)
        self.error = error


@dataclass(frozen=True, slots=True)
class ParsedGradingResult:
    output: GradingOutput


class GradingParser(Protocol):
    def __call__(self, raw_output: str) -> ParsedGradingResult: ...


def parse_grading_output(raw_output: str) -> ParsedGradingResult:
    normalized_raw_output = raw_output.strip()

    try:
        payload = json.loads(normalized_raw_output)
    except JSONDecodeError as exc:
        raise GradingParseFailure(
            GradingParseError(
                code=GradingParseErrorCode.INVALID_JSON,
                message="Provider output is not valid JSON.",
                raw_output=normalized_raw_output,
                details=[str(exc)],
            )
        ) from exc

    if not isinstance(payload, dict):
        raise GradingParseFailure(
            GradingParseError(
                code=GradingParseErrorCode.INVALID_ROOT,
                message="Provider output must decode to a JSON object.",
                raw_output=normalized_raw_output,
            )
        )

    try:
        validated_output = GradingOutput.model_validate(payload)
    except ValidationError as exc:
        raise GradingParseFailure(
            _build_validation_parse_error(exc, normalized_raw_output)
        ) from exc

    return ParsedGradingResult(output=validated_output)


def _build_validation_parse_error(
    exc: ValidationError,
    raw_output: str,
) -> GradingParseError:
    details: list[str] = []
    has_missing_required_field = False
    has_intent_label_mismatch = False

    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ()))
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
