from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from app.core.constants import INTENT_CODE_TO_LABEL
from app.models.enums import EscalationType
from app.schemas.analytics import SchemaModel

_REASONING_FIELDS = (
    "relevancy_reasoning",
    "accuracy_reasoning",
    "completeness_reasoning",
    "clarity_reasoning",
    "tone_reasoning",
    "resolution_reasoning",
    "repetition_reasoning",
    "loop_detected_reasoning",
    "satisfaction_reasoning",
    "frustration_reasoning",
    "user_relevancy_reasoning",
    "escalation_occurred_reasoning",
    "escalation_type_reasoning",
    "intent_reasoning",
)

ScoreValue = Annotated[StrictInt, Field(ge=1, le=10)]
BooleanValue = StrictBool


class GradingParseErrorCode(str, Enum):
    INVALID_JSON = "invalid_json"
    INVALID_ROOT = "invalid_root"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    FIELD_VALIDATION_ERROR = "field_validation_error"
    INTENT_LABEL_MISMATCH = "intent_label_mismatch"


class GradingParseError(SchemaModel):
    code: GradingParseErrorCode = Field(
        description="Stable parser failure code for malformed model output.",
    )
    message: str = Field(
        min_length=1,
        description="Human-readable summary of the parsing failure.",
    )
    raw_output: str | None = Field(
        default=None,
        description="Optional raw provider output captured for debugging.",
    )
    details: list[str] = Field(
        default_factory=list,
        description="Optional field-level validation details.",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank.")
        return normalized

    @field_validator("raw_output")
    @classmethod
    def normalize_raw_output(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("details")
    @classmethod
    def normalize_details(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized:
                raise ValueError("details must not contain blank items.")
            normalized_values.append(normalized)
        return normalized_values


class GradingOutput(SchemaModel):
    relevancy_score: ScoreValue
    relevancy_reasoning: str = Field(min_length=1)
    accuracy_score: ScoreValue
    accuracy_reasoning: str = Field(min_length=1)
    completeness_score: ScoreValue
    completeness_reasoning: str = Field(min_length=1)
    clarity_score: ScoreValue
    clarity_reasoning: str = Field(min_length=1)
    tone_score: ScoreValue
    tone_reasoning: str = Field(min_length=1)
    resolution: BooleanValue
    resolution_reasoning: str = Field(min_length=1)
    repetition_score: ScoreValue
    repetition_reasoning: str = Field(min_length=1)
    loop_detected: BooleanValue
    loop_detected_reasoning: str = Field(min_length=1)
    satisfaction_score: ScoreValue
    satisfaction_reasoning: str = Field(min_length=1)
    frustration_score: ScoreValue
    frustration_reasoning: str = Field(min_length=1)
    user_relevancy: BooleanValue
    user_relevancy_reasoning: str = Field(min_length=1)
    escalation_occurred: BooleanValue
    escalation_occurred_reasoning: str = Field(min_length=1)
    escalation_type: EscalationType = Field(
        description="Canonical escalation type classification.",
    )
    escalation_type_reasoning: str = Field(min_length=1)
    intent_code: str = Field(
        min_length=1,
        description="Canonical Milestone 2 intent code.",
    )
    intent_label: str = Field(
        min_length=1,
        description="Canonical display label for the selected intent code.",
    )
    intent_reasoning: str = Field(
        min_length=1,
        description="English reasoning supporting the selected dominant intent.",
    )

    @field_validator(*_REASONING_FIELDS)
    @classmethod
    def validate_reasoning_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reasoning fields must not be blank.")
        return normalized

    @field_validator("intent_code")
    @classmethod
    def validate_intent_code(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in INTENT_CODE_TO_LABEL:
            raise ValueError("intent_code must be a supported canonical intent code.")
        return normalized

    @field_validator("intent_label")
    @classmethod
    def validate_intent_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("intent_label must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_intent_label_alignment(self) -> "GradingOutput":
        expected_label = INTENT_CODE_TO_LABEL[self.intent_code]
        if self.intent_label != expected_label:
            raise ValueError(
                f"intent_label must match canonical label '{expected_label}' "
                f"for intent_code '{self.intent_code}'."
            )
        return self
