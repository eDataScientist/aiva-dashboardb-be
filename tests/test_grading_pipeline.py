from __future__ import annotations

import json
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION
from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.models.enums import EscalationType, IdentityType
from app.schemas.grading import GradingOutput
from app.schemas.grading_prompts import PromptDomain
from app.services.grading_extraction import CustomerDayCandidate
from app.services.grading_parser import parse_prompt_execution_results
from app.services.grading_pipeline import (
    GradeCustomerDayFailureCode,
    GradingPipelineDependencies,
    grade_customer_day,
)
from app.services.grading_persistence import upsert_customer_day_grade
from app.services.grading_prompt import build_prompt_execution_plan
from app.services.grading_provider import GradingProviderError, build_grading_provider


def _candidate(
    *,
    identity_type: IdentityType = IdentityType.PHONE,
    conversation_identity: str = "+971500000100",
    grade_date: date = date(2026, 3, 9),
) -> CustomerDayCandidate:
    return CustomerDayCandidate(
        identity_type=identity_type,
        conversation_identity=conversation_identity,
        grade_date=grade_date,
    )


def _grading_output(**overrides: object) -> GradingOutput:
    payload: dict[str, object] = {
        "relevancy_score": 8,
        "relevancy_reasoning": "The assistant stayed focused on the customer's request.",
        "accuracy_score": 8,
        "accuracy_reasoning": "The policy guidance matched the visible transcript.",
        "completeness_score": 7,
        "completeness_reasoning": "The answer covered the main next steps with small gaps.",
        "clarity_score": 8,
        "clarity_reasoning": "The wording was direct and easy to follow.",
        "tone_score": 9,
        "tone_reasoning": "The tone remained professional and calm.",
        "resolution": True,
        "resolution_reasoning": "The issue appears resolved from the final exchange.",
        "repetition_score": 8,
        "repetition_reasoning": "The assistant did not repeat the same response loop.",
        "loop_detected": False,
        "loop_detected_reasoning": "The transcript progressed without stalling.",
        "satisfaction_score": 8,
        "satisfaction_reasoning": "The customer signals suggested acceptance of the answer.",
        "frustration_score": 2,
        "frustration_reasoning": "There were no strong signs of frustration.",
        "user_relevancy": True,
        "user_relevancy_reasoning": "This was a genuine insurance support request.",
        "escalation_occurred": False,
        "escalation_occurred_reasoning": "No human handoff was required.",
        "escalation_type": EscalationType.NONE,
        "escalation_type_reasoning": "The conversation did not escalate.",
        "intent_code": "policy_inquiry",
        "intent_label": "Policy Inquiry",
        "intent_reasoning": "The customer primarily asked for policy details.",
    }
    payload.update(overrides)
    return GradingOutput.model_validate(payload)


def _partial_prompt_payloads(**overrides: object) -> dict[str, dict[str, object]]:
    payload = _grading_output(**overrides).model_dump(mode="json")
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


def _settings() -> Settings:
    return Settings(
        database_url="sqlite:///tests.db",
        auth_jwt_secret="x" * 32,
        auth_jwt_algorithm="HS256",
        auth_access_token_expire_minutes=60,
        grading_provider="mock",
        grading_model=GRADING_DEFAULT_MODEL,
        grading_request_timeout_seconds=5,
        grading_max_retries=1,
        grading_prompt_version=GRADING_DEFAULT_PROMPT_VERSION,
    )


def _chat(
    *,
    created_at: datetime,
    customer_phone: str,
    message: str,
    direction: str,
    intent: str | None = None,
    message_type: str = "text",
) -> ChatMessage:
    return ChatMessage(
        created_at=created_at,
        customer_phone=customer_phone,
        message=message,
        direction=direction,
        channel="whatsapp",
        message_type=message_type,
        intent=intent,
        escalated="no",
    )


async def _seed_transcript(db_session, candidate: CustomerDayCandidate) -> None:
    db_session.add_all(
        [
            _chat(
                created_at=datetime(2026, 3, 9, 8, 0, 0),
                customer_phone=candidate.conversation_identity,
                message="I need help updating my motor policy.",
                direction="inbound",
                intent="Policy Update",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 8, 1, 0),
                customer_phone=candidate.conversation_identity,
                message="Sure, I can help with the policy change requirements.",
                direction="outbound",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 8, 2, 0),
                customer_phone=candidate.conversation_identity,
                message="The car is financed. Does that change anything?",
                direction="customer",
                intent="Policy Update",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 8, 3, 0),
                customer_phone=candidate.conversation_identity,
                message="Yes, I will also need the bank letter and Emirates ID copy.",
                direction="outbound",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 8, 4, 0),
                customer_phone=candidate.conversation_identity,
                message="Understood, please send the renewal requirements.",
                direction="in",
                intent="Policy Update",
            ),
        ]
    )
    await db_session.commit()


async def _seed_partial_transcript(db_session, candidate: CustomerDayCandidate) -> None:
    db_session.add_all(
        [
            _chat(
                created_at=datetime(2026, 3, 9, 9, 0, 0),
                customer_phone=candidate.conversation_identity,
                message="Hi",
                direction="inbound",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 9, 1, 0),
                customer_phone=candidate.conversation_identity,
                message="Hello, how can I help?",
                direction="outbound",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 9, 2, 0),
                customer_phone=candidate.conversation_identity,
                message="Need renewal details.",
                direction="customer",
            ),
            _chat(
                created_at=datetime(2026, 3, 9, 9, 3, 0),
                customer_phone=candidate.conversation_identity,
                message="Please share the vehicle policy number.",
                direction="outbound",
            ),
        ]
    )
    await db_session.commit()


def _build_prompt_pack_provider(
    payloads: dict[str, dict[str, object]],
):
    async def provider(request) -> str:
        return json.dumps(payloads[request.prompt.prompt_key])

    return provider


@pytest.mark.asyncio
async def test_upsert_customer_day_grade_inserts_complete_grade_row(db_session) -> None:
    candidate = _candidate()
    output = _grading_output()

    await upsert_customer_day_grade(db_session, candidate, output)

    grade = await db_session.scalar(
        select(ConversationGrade).where(
            ConversationGrade.identity_type == candidate.identity_type.value,
            ConversationGrade.conversation_identity == candidate.conversation_identity,
            ConversationGrade.grade_date == candidate.grade_date,
        )
    )

    assert grade is not None
    assert grade.phone_number == candidate.conversation_identity
    assert grade.intent_code == "policy_inquiry"
    assert grade.intent_label == "Policy Inquiry"
    assert grade.relevancy_score == 8
    assert grade.resolution is True
    assert grade.escalation_type == EscalationType.NONE.value
    assert grade.intent_reasoning == "The customer primarily asked for policy details."


@pytest.mark.asyncio
async def test_upsert_customer_day_grade_updates_legacy_phone_row_without_duplication(
    db_session,
) -> None:
    candidate = _candidate()
    existing = ConversationGrade(
        phone_number=candidate.conversation_identity,
        grade_date=candidate.grade_date,
        intent_code="unknown",
        intent_label="Unknown",
        intent_reasoning="Older value.",
        relevancy_score=3,
        relevancy_reasoning="Older value.",
    )
    db_session.add(existing)
    await db_session.flush()
    existing_id = existing.id

    updated_output = _grading_output(
        accuracy_score=9,
        accuracy_reasoning="Updated rerun output.",
        intent_code="general_inquiry",
        intent_label="General Inquiry",
        intent_reasoning="Updated rerun intent.",
    )

    await upsert_customer_day_grade(db_session, candidate, updated_output)

    grade_count = await db_session.scalar(select(func.count()).select_from(ConversationGrade))
    updated = await db_session.get(ConversationGrade, existing_id)

    assert grade_count == 1
    assert updated is not None
    assert updated.id == existing_id
    assert updated.identity_type == IdentityType.PHONE.value
    assert updated.conversation_identity == candidate.conversation_identity
    assert updated.phone_number == candidate.conversation_identity
    assert updated.intent_code == "general_inquiry"
    assert updated.intent_label == "General Inquiry"
    assert updated.accuracy_score == 9
    assert updated.accuracy_reasoning == "Updated rerun output."


@pytest.mark.asyncio
async def test_grade_customer_day_runs_full_pipeline_and_persists_result(db_session) -> None:
    candidate = _candidate(conversation_identity="+971500000101")
    await _seed_transcript(db_session, candidate)
    provider = build_grading_provider(settings=_settings())

    result = await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=provider,
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )

    grade = await db_session.scalar(
        select(ConversationGrade).where(
            ConversationGrade.identity_type == candidate.identity_type.value,
            ConversationGrade.conversation_identity == candidate.conversation_identity,
            ConversationGrade.grade_date == candidate.grade_date,
        )
    )

    assert result.candidate == candidate
    assert result.ok is True
    assert len(result.transcript.messages) == 5
    assert result.prompt_plan.metadata["bundle_count"] == 5
    assert result.prompt_plan.metadata["message_count"] == 5
    assert [bundle.prompt_key for bundle, _ in result.raw_outputs] == [
        prompt_domain.value for prompt_domain in PromptDomain
    ]
    assert result.output.intent_code == "general_inquiry"
    assert grade is not None
    assert grade.intent_code == "general_inquiry"
    assert grade.relevancy_score == 8


@pytest.mark.asyncio
async def test_grade_customer_day_returns_provider_failure_result(db_session) -> None:
    candidate = _candidate(conversation_identity="+971500000102")
    await _seed_transcript(db_session, candidate)

    async def failing_provider(_request) -> str:
        raise GradingProviderError("provider timeout")

    result = await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=failing_provider,
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )

    grade_count = await db_session.scalar(select(func.count()).select_from(ConversationGrade))

    assert result.ok is False
    assert result.code == GradeCustomerDayFailureCode.PROVIDER_ERROR
    assert result.message == "provider timeout"
    assert result.prompt_plan is not None
    assert result.raw_outputs == ()
    assert grade_count == 0


@pytest.mark.asyncio
async def test_grade_customer_day_returns_parse_failure_result_without_partial_write(
    db_session,
) -> None:
    candidate = _candidate(conversation_identity="+971500000103")
    await _seed_transcript(db_session, candidate)
    payloads = _partial_prompt_payloads()

    async def invalid_payload_provider(request) -> str:
        if request.prompt.prompt_key == PromptDomain.AI_PERFORMANCE.value:
            return '{"relevancy_score": 9}'
        return json.dumps(payloads[request.prompt.prompt_key])

    result = await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=invalid_payload_provider,
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )

    grade_count = await db_session.scalar(select(func.count()).select_from(ConversationGrade))

    assert result.ok is False
    assert result.code == GradeCustomerDayFailureCode.PARSE_ERROR
    assert result.parse_error is not None
    assert len(result.raw_outputs) == 5
    assert "ai_performance.tone_score" in " ".join(result.details)
    assert grade_count == 0


@pytest.mark.asyncio
async def test_grade_customer_day_returns_empty_transcript_failure_without_provider_call(
    db_session,
) -> None:
    candidate = _candidate(conversation_identity="+971500000105")
    provider_called = False

    async def provider(_request) -> str:
        nonlocal provider_called
        provider_called = True
        return json.dumps(_grading_output().model_dump(mode="json"))

    result = await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=provider,
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )

    grade_count = await db_session.scalar(select(func.count()).select_from(ConversationGrade))

    assert result.ok is False
    assert result.code == GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT
    assert result.prompt_plan is None
    assert provider_called is False
    assert grade_count == 0


@pytest.mark.asyncio
async def test_grade_customer_day_requires_three_inbound_human_messages(
    db_session,
) -> None:
    candidate = _candidate(conversation_identity="+971500000106")
    await _seed_partial_transcript(db_session, candidate)
    provider_called = False

    async def provider(_request) -> str:
        nonlocal provider_called
        provider_called = True
        return json.dumps(_grading_output().model_dump(mode="json"))

    result = await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=provider,
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )

    grade_count = await db_session.scalar(select(func.count()).select_from(ConversationGrade))

    assert result.ok is False
    assert result.code == GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT
    assert (
        result.message
        == "Customer-day transcript must include at least 3 inbound human messages before grading."
    )
    assert result.prompt_plan is None
    assert provider_called is False
    assert grade_count == 0


@pytest.mark.asyncio
async def test_grade_customer_day_rerun_overwrites_existing_grade_without_duplication(
    db_session,
) -> None:
    candidate = _candidate(conversation_identity="+971500000104")
    await _seed_transcript(db_session, candidate)
    first_payloads = _partial_prompt_payloads(
        clarity_score=5,
        clarity_reasoning="First run clarity score.",
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        intent_reasoning="First run intent.",
    )
    second_payloads = _partial_prompt_payloads(
        clarity_score=9,
        clarity_reasoning="Second run clarity score.",
        intent_code="general_inquiry",
        intent_label="General Inquiry",
        intent_reasoning="Second run intent.",
    )

    await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=_build_prompt_pack_provider(first_payloads),
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )
    await grade_customer_day(
        db_session,
        candidate,
        GradingPipelineDependencies(
            settings=_settings(),
            prompt_planner=build_prompt_execution_plan,
            provider=_build_prompt_pack_provider(second_payloads),
            parser=parse_prompt_execution_results,
            persistence=upsert_customer_day_grade,
        ),
    )

    grades = (
        await db_session.execute(
            select(ConversationGrade).where(
                ConversationGrade.identity_type == candidate.identity_type.value,
                ConversationGrade.conversation_identity == candidate.conversation_identity,
                ConversationGrade.grade_date == candidate.grade_date,
            )
        )
    ).scalars().all()

    assert len(grades) == 1
    assert grades[0].clarity_score == 9
    assert grades[0].clarity_reasoning == "Second run clarity score."
    assert grades[0].intent_code == "general_inquiry"
    assert grades[0].intent_label == "General Inquiry"
    assert grades[0].intent_reasoning == "Second run intent."
