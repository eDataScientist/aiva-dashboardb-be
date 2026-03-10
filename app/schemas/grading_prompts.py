from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.models.enums import EscalationType
from app.schemas.analytics import SchemaModel


ScoreValue = Annotated[StrictInt, Field(ge=1, le=10)]


class PromptDomain(str, Enum):
    AI_PERFORMANCE = "ai_performance"
    CONVERSATION_HEALTH = "conversation_health"
    USER_SIGNALS = "user_signals"
    ESCALATION = "escalation"
    INTENT = "intent"


class PromptTemplateSpec(SchemaModel):
    prompt_key: PromptDomain = Field(
        description="Stable prompt-domain key used by the grading prompt pack.",
    )
    template_file: str = Field(
        min_length=1,
        description="Markdown template filename for this prompt domain.",
    )
    output_fields: tuple[str, ...] = Field(
        min_length=1,
        description="Canonical output fields owned by this prompt domain.",
    )
    include_system_prompt: bool = Field(
        default=False,
        description="Whether runtime rendering injects system_prompt.md into this template.",
    )
    required_placeholders: tuple[str, ...] = Field(
        default=("conversation",),
        description="Placeholder tokens required in the markdown template.",
    )

    @model_validator(mode="after")
    def validate_prompt_template_spec(self) -> "PromptTemplateSpec":
        if self.include_system_prompt and "system_prompt" not in self.required_placeholders:
            raise ValueError(
                "required_placeholders must include 'system_prompt' when include_system_prompt is true."
            )
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValueError("output_fields must not contain duplicates.")
        if len(set(self.required_placeholders)) != len(self.required_placeholders):
            raise ValueError("required_placeholders must not contain duplicates.")
        return self


class PromptPackManifest(SchemaModel):
    version: str = Field(
        min_length=1,
        description="Active prompt-pack version identifier.",
    )
    system_prompt_file: str = Field(
        default="system_prompt.md",
        min_length=1,
        description="Shared system prompt filename for the prompt pack.",
    )
    prompt_order: tuple[PromptDomain, ...] = Field(
        min_length=1,
        description="Deterministic execution order for the prompt domains.",
    )
    prompt_templates: tuple[PromptTemplateSpec, ...] = Field(
        min_length=1,
        description="Prompt template specifications for every prompt domain in the pack.",
    )

    @model_validator(mode="after")
    def validate_prompt_pack_manifest(self) -> "PromptPackManifest":
        expected_prompt_order = tuple(PromptDomain)
        template_keys = tuple(template.prompt_key for template in self.prompt_templates)
        if len(set(template_keys)) != len(template_keys):
            raise ValueError("prompt_templates must contain unique prompt_key values.")
        if self.prompt_order != expected_prompt_order:
            raise ValueError(
                "prompt_order must contain the full fixed prompt-domain sequence."
            )
        if template_keys != expected_prompt_order:
            raise ValueError(
                "prompt_templates must contain the full fixed prompt-domain sequence."
            )
        if template_keys != self.prompt_order:
            raise ValueError(
                "prompt_order must match the ordered prompt_key values from prompt_templates."
            )
        return self


class AIPerformancePromptOutput(SchemaModel):
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


class ConversationHealthPromptOutput(SchemaModel):
    resolution: StrictBool
    resolution_reasoning: str = Field(min_length=1)
    repetition_score: ScoreValue
    repetition_reasoning: str = Field(min_length=1)
    loop_detected: StrictBool
    loop_detected_reasoning: str = Field(min_length=1)


class UserSignalsPromptOutput(SchemaModel):
    satisfaction_score: ScoreValue
    satisfaction_reasoning: str = Field(min_length=1)
    frustration_score: ScoreValue
    frustration_reasoning: str = Field(min_length=1)
    user_relevancy: StrictBool
    user_relevancy_reasoning: str = Field(min_length=1)


class EscalationPromptOutput(SchemaModel):
    escalation_occurred: StrictBool
    escalation_occurred_reasoning: str = Field(min_length=1)
    escalation_type: EscalationType = Field(
        description="Canonical escalation type classification.",
    )
    escalation_type_reasoning: str = Field(min_length=1)


class IntentPromptOutput(SchemaModel):
    intent_label: str = Field(
        min_length=1,
        description="Legacy-compatible prompt output label used for canonical intent normalization.",
    )
    intent_reasoning: str = Field(min_length=1)


class PromptPackPartialOutputs(SchemaModel):
    ai_performance: AIPerformancePromptOutput
    conversation_health: ConversationHealthPromptOutput
    user_signals: UserSignalsPromptOutput
    escalation: EscalationPromptOutput
    intent: IntentPromptOutput
