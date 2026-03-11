from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.config import Settings
from app.core.constants import GRADING_DEFAULT_PROMPT_VERSION
from app.models.enums import IdentityType
from app.schemas.grading_prompts import PromptDomain
from app.services.grading_extraction import (
    CustomerDayCandidate,
    CustomerDayTranscript,
    TranscriptMessage,
)
from app.services.grading_prompt import build_grading_prompt, build_prompt_execution_plan


def _build_transcript() -> CustomerDayTranscript:
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
            TranscriptMessage(
                chat_id=102,
                created_at=datetime(2026, 3, 8, 8, 31, tzinfo=timezone.utc),
                direction="outbound",
                channel="whatsapp",
                message_type="image",
                message=None,
                intent=None,
                escalated=False,
                normalized_content="[image attachment]",
                transcript_line=(
                    "2026-03-08T08:31:00+00:00 | direction=outbound | "
                    "channel=whatsapp | message_type=image | escalated=false | "
                    "intent=<none> | content=[image attachment]"
                ),
            ),
        ),
        transcript_text=(
            "2026-03-08T08:30:00+00:00 | direction=inbound | channel=whatsapp | "
            "message_type=text | escalated=false | intent=Renewal | "
            "content=I need help with my motor policy renewal.\n"
            "2026-03-08T08:31:00+00:00 | direction=outbound | channel=whatsapp | "
            "message_type=image | escalated=false | intent=<none> | "
            "content=[image attachment]"
        ),
    )

def test_build_grading_prompt_includes_contract_and_taxonomy() -> None:
    bundle = build_grading_prompt(_build_transcript())

    assert bundle.prompt_version == GRADING_DEFAULT_PROMPT_VERSION
    assert "Return exactly one JSON object and nothing else." in bundle.system_prompt
    assert '"relevancy_score": integer 1-10' in bundle.system_prompt
    assert '"escalation_type": one of Natural, Failure, None' in bundle.system_prompt
    assert '"policy_inquiry" -> "Policy Inquiry"' in bundle.system_prompt
    assert '"unknown" -> "Unknown"' in bundle.system_prompt
    assert bundle.metadata["message_count"] == 2


def test_build_grading_prompt_serializes_transcript_context() -> None:
    bundle = build_grading_prompt(_build_transcript())

    assert "- identity_type: phone" in bundle.user_prompt
    assert "- conversation_identity: +971500000001" in bundle.user_prompt
    assert "1. 2026-03-08T08:30:00+00:00" in bundle.user_prompt
    assert "content=I need help with my motor policy renewal." in bundle.user_prompt
    assert "message_type=image" in bundle.user_prompt
    assert "content=[image attachment]" in bundle.user_prompt


def test_build_grading_prompt_uses_active_settings_prompt_version() -> None:
    settings = Settings.model_construct(grading_prompt_version="v-custom")
    bundle = build_grading_prompt(_build_transcript(), settings=settings)

    assert bundle.prompt_version == "v-custom"


def test_build_prompt_execution_plan_uses_prompt_pack_manifest_order() -> None:
    plan = build_prompt_execution_plan(_build_transcript())

    assert plan.prompt_version == GRADING_DEFAULT_PROMPT_VERSION
    assert plan.metadata["bundle_count"] == 5
    assert plan.metadata["prompt_order"] == [
        "ai_performance",
        "conversation_health",
        "user_signals",
        "escalation",
        "intent",
    ]
    assert [bundle.prompt_key for bundle in plan.bundles] == [
        "ai_performance",
        "conversation_health",
        "user_signals",
        "escalation",
        "intent",
    ]
    assert plan.bundles[0].system_prompt is None
    assert plan.bundles[1].system_prompt is None
    assert plan.bundles[3].system_prompt is None
    assert "{{conversation}}" not in plan.bundles[0].user_prompt
    assert "{{system_prompt}}" not in plan.bundles[0].user_prompt
    assert (
        plan.bundles[0].user_prompt.count(
            "You are **AIVA**, Arabia Insurance UAE's virtual assistant."
        )
        == 1
    )
    assert (
        "You are **AIVA**, Arabia Insurance UAE's virtual assistant."
        not in plan.bundles[1].user_prompt
    )
    assert plan.bundles[0].prompt_domain is PromptDomain.AI_PERFORMANCE
    assert plan.bundles[0].template_file == "ai_performance_judge.md"
    assert plan.bundles[0].include_system_prompt is True
    assert plan.bundles[1].include_system_prompt is False
    assert plan.bundles[4].output_fields == ("intent_label", "intent_reasoning")
    assert plan.bundles[3].metadata["prompt_sequence"] == 4
    assert plan.bundles[3].metadata["template_file"] == "escalation.md"
