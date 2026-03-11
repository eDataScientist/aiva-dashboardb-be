from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.core.constants import INTENT_CODE_TO_LABEL
from app.schemas.grading_prompts import PromptDomain, PromptTemplateSpec
from app.services.grading_extraction import CustomerDayTranscript, TranscriptMessage
from app.services.grading_prompt_assets import LoadedPromptPack, load_prompt_pack

_INTENT_TAXONOMY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Policy Related",
        (
            "policy_inquiry",
            "policy_purchase",
            "policy_modification",
            "policy_cancellation",
        ),
    ),
    (
        "Claims Related",
        (
            "claims_submission",
            "claims_follow_up",
            "claims_dispute",
        ),
    ),
    (
        "Billing & Payments",
        (
            "payment_inquiry",
            "payment_issue",
        ),
    ),
    (
        "Documents & Admin",
        (
            "document_request",
            "account_profile_update",
        ),
    ),
    (
        "Support & Complaints",
        (
            "general_inquiry",
            "complaint",
            "escalation_request",
        ),
    ),
    (
        "Non-genuine",
        ("wasteful", "unknown"),
    ),
)

_REQUIRED_OUTPUT_FIELDS: tuple[tuple[str, str], ...] = (
    ("relevancy_score", "integer 1-10"),
    ("relevancy_reasoning", "non-empty English string"),
    ("accuracy_score", "integer 1-10"),
    ("accuracy_reasoning", "non-empty English string"),
    ("completeness_score", "integer 1-10"),
    ("completeness_reasoning", "non-empty English string"),
    ("clarity_score", "integer 1-10"),
    ("clarity_reasoning", "non-empty English string"),
    ("tone_score", "integer 1-10"),
    ("tone_reasoning", "non-empty English string"),
    ("resolution", "boolean"),
    ("resolution_reasoning", "non-empty English string"),
    ("repetition_score", "integer 1-10"),
    ("repetition_reasoning", "non-empty English string"),
    ("loop_detected", "boolean"),
    ("loop_detected_reasoning", "non-empty English string"),
    ("satisfaction_score", "integer 1-10"),
    ("satisfaction_reasoning", "non-empty English string"),
    ("frustration_score", "integer 1-10"),
    ("frustration_reasoning", "non-empty English string"),
    ("user_relevancy", "boolean"),
    ("user_relevancy_reasoning", "non-empty English string"),
    ("escalation_occurred", "boolean"),
    ("escalation_occurred_reasoning", "non-empty English string"),
    ("escalation_type", "one of Natural, Failure, None"),
    ("escalation_type_reasoning", "non-empty English string"),
    ("intent_code", "canonical intent code"),
    ("intent_label", "canonical label matching intent_code"),
    ("intent_reasoning", "non-empty English string"),
)

_SYSTEM_PROMPT_TEMPLATE = """You are the internal Arabia Insurance AI grading judge.

Grade exactly one customer-day transcript. Use only evidence present in the transcript.
Return exactly one JSON object and nothing else. Do not wrap the JSON in markdown.
Do not add extra keys, comments, prose, or trailing text.
All reasoning fields must be non-empty English sentences.

Scoring rubric:
- relevancy_score: how well the assistant addressed the customer's actual request.
- accuracy_score: factual and procedural correctness for the insurance context.
- completeness_score: how fully the assistant answered the customer's need.
- clarity_score: clarity and readability of the assistant's wording.
- tone_score: professionalism and appropriateness of tone.
- resolution: true only if the customer's need appears fully resolved in the transcript.
- repetition_score: how well the assistant avoided repetitive or looping responses.
- loop_detected: true when the conversation entered a circular or stalled pattern.
- satisfaction_score: inferred customer satisfaction from the conversation evidence.
- frustration_score: inferred customer frustration from the conversation evidence.
- user_relevancy: true for genuine insurance interactions, false for spam, irrelevant, or wasteful interactions.
- escalation_occurred: true if a human handoff happened or was explicitly requested.
- escalation_type: use "Natural" for a planned/appropriate handoff, "Failure" for a bot breakdown or inability to cope, and "None" when no escalation happened.

Intent taxonomy:
{intent_taxonomy}

Output contract:
- Score fields must be integers in the inclusive range 1 through 10.
- Boolean fields must be JSON booleans true or false.
- intent_code must be one of the canonical codes listed above.
- intent_label must exactly match the canonical label for the chosen intent_code.
- If the conversation is spam, irrelevant, or lacks a clear business intent, use intent_code "unknown" or "wasteful" as appropriate.
- Every required field must be present. Missing fields are not allowed.

Required JSON fields:
{required_fields}
"""


@dataclass(frozen=True, slots=True)
class PromptBundle:
    system_prompt: str | None
    user_prompt: str
    prompt_version: str
    prompt_key: str = "grading"
    prompt_domain: PromptDomain | None = None
    output_fields: tuple[str, ...] = ()
    template_file: str | None = None
    include_system_prompt: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class GradingPromptBuilder(Protocol):
    def __call__(self, transcript: CustomerDayTranscript) -> PromptBundle: ...


@dataclass(frozen=True, slots=True)
class PromptExecutionPlan:
    prompt_version: str
    bundles: tuple[PromptBundle, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


class MultiPromptExecutionPlanner(Protocol):
    def __call__(self, transcript: CustomerDayTranscript) -> PromptExecutionPlan: ...


def build_grading_prompt(
    transcript: CustomerDayTranscript,
    *,
    settings: Settings | None = None,
) -> PromptBundle:
    resolved_settings = settings or get_settings()
    return PromptBundle(
        system_prompt=_build_system_prompt(),
        user_prompt=_build_user_prompt(transcript),
        prompt_version=resolved_settings.grading_prompt_version,
        metadata=_build_prompt_metadata(transcript),
    )


def build_prompt_execution_plan(
    transcript: CustomerDayTranscript,
    *,
    prompt_pack: LoadedPromptPack | None = None,
) -> PromptExecutionPlan:
    loaded_prompt_pack = prompt_pack or load_prompt_pack()
    metadata = _build_prompt_metadata(transcript)
    bundles = tuple(
        _build_prompt_pack_bundle(
            transcript=transcript,
            prompt_pack=loaded_prompt_pack,
            template=template,
            base_metadata=metadata,
            sequence_index=sequence_index,
        )
        for sequence_index, template in enumerate(
            loaded_prompt_pack.manifest.prompt_templates,
            start=1,
        )
    )
    return PromptExecutionPlan(
        prompt_version=loaded_prompt_pack.manifest.version,
        bundles=bundles,
        metadata={
            **metadata,
            "bundle_count": len(bundles),
            "prompt_order": [bundle.prompt_key for bundle in bundles],
        },
    )


def _build_system_prompt() -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        intent_taxonomy=_render_intent_taxonomy(),
        required_fields=_render_required_fields(),
    )


def _build_user_prompt(transcript: CustomerDayTranscript) -> str:
    return "\n".join(
        (
            "Grade the following customer-day transcript.",
            "Conversation metadata:",
            f"- identity_type: {transcript.candidate.identity_type.value}",
            f"- conversation_identity: {transcript.candidate.conversation_identity}",
            f"- grade_date: {transcript.candidate.grade_date.isoformat()}",
            f"- message_count: {len(transcript.messages)}",
            "",
            "Return only the JSON object defined in the system instructions.",
            "",
            "Transcript:",
            _render_transcript_messages(transcript),
        )
    )


def _build_prompt_metadata(transcript: CustomerDayTranscript) -> dict[str, Any]:
    return {
        "identity_type": transcript.candidate.identity_type.value,
        "conversation_identity": transcript.candidate.conversation_identity,
        "grade_date": transcript.candidate.grade_date.isoformat(),
        "message_count": len(transcript.messages),
    }


def _render_intent_taxonomy() -> str:
    lines: list[str] = []
    for category, codes in _INTENT_TAXONOMY_GROUPS:
        lines.append(f"- {category}:")
        for code in codes:
            lines.append(f'  - "{code}" -> "{INTENT_CODE_TO_LABEL[code]}"')
    return "\n".join(lines)


def _render_required_fields() -> str:
    return "\n".join(
        f'- "{field_name}": {field_contract}'
        for field_name, field_contract in _REQUIRED_OUTPUT_FIELDS
    )


def _render_transcript_messages(transcript: CustomerDayTranscript) -> str:
    if not transcript.messages:
        return "- No transcript messages were provided."

    transcript_lines = [
        line.strip()
        for line in transcript.transcript_text.splitlines()
        if line.strip()
    ]
    if transcript_lines:
        return "\n".join(
            f"{index}. {line}" for index, line in enumerate(transcript_lines, start=1)
        )

    lines: list[str] = []
    for index, message in enumerate(transcript.messages, start=1):
        lines.append(f"{index}. {_render_transcript_line(message)}")
    return "\n".join(lines)


def _render_transcript_line(message: TranscriptMessage) -> str:
    normalized_line = message.transcript_line.strip()
    if normalized_line:
        return normalized_line

    intent_token = message.intent.strip() if message.intent and message.intent.strip() else "<none>"
    return (
        f"{message.created_at.isoformat()} | "
        f"direction={message.direction} | "
        f"channel={message.channel} | "
        f"message_type={message.message_type} | "
        f"escalated={_format_escalated_token(message.escalated)} | "
        f"intent={intent_token} | "
        f"content={message.normalized_content or _render_message_content(message.message, message.message_type)}"
    )


def _render_message_content(message: str | None, message_type: str | None) -> str:
    if message is None or not message.strip():
        return f"[{message_type or 'unknown'} payload omitted]"
    return message.strip()


def _format_escalated_token(value: bool | None) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def _render_prompt_template(
    *,
    template_text: str,
    conversation_text: str,
    system_prompt_text: str | None,
) -> str:
    rendered = template_text.replace("{{conversation}}", conversation_text)
    if system_prompt_text is not None:
        rendered = rendered.replace("{{system_prompt}}", system_prompt_text)
    return rendered


def _build_prompt_pack_bundle(
    *,
    transcript: CustomerDayTranscript,
    prompt_pack: LoadedPromptPack,
    template: PromptTemplateSpec,
    base_metadata: dict[str, Any],
    sequence_index: int,
) -> PromptBundle:
    system_prompt_text = (
        prompt_pack.system_prompt_text if template.include_system_prompt else None
    )
    prompt_metadata = {
        **base_metadata,
        "prompt_key": template.prompt_key.value,
        "template_file": template.template_file,
        "include_system_prompt": template.include_system_prompt,
        "output_fields": list(template.output_fields),
        "prompt_sequence": sequence_index,
    }
    return PromptBundle(
        system_prompt=None,
        user_prompt=_render_prompt_template(
            template_text=prompt_pack.get_template(template.prompt_key),
            conversation_text=_render_transcript_messages(transcript),
            system_prompt_text=system_prompt_text,
        ),
        prompt_version=prompt_pack.manifest.version,
        prompt_key=template.prompt_key.value,
        prompt_domain=template.prompt_key,
        output_fields=template.output_fields,
        template_file=template.template_file,
        include_system_prompt=template.include_system_prompt,
        metadata=prompt_metadata,
    )
