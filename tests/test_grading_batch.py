from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.constants import GRADING_DEFAULT_MODEL, GRADING_DEFAULT_PROMPT_VERSION
from app.models.account import Account
from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.models.grading_runs import GradingRun, GradingRunItem
from app.schemas.grading import EscalationType, GradingOutput
from app.schemas.grading_runs import (
    GradingRunItemStatusSchema,
    GradingRunModeSchema,
    GradingRunStatusSchema,
    GradingRunTriggerRequest,
    GradingRunTriggerTypeSchema,
)
from app.services.grading_batch import (
    GradingBatchExecutionRequest,
    GradingBatchWindow,
    build_manual_batch_execution_request,
    check_existing_grades,
    compute_advisory_lock_key,
    execute_grading_batch,
    get_previous_gst_business_day,
    plan_batch_candidates,
    plan_manual_batch_window,
    plan_scheduled_batch_window,
)
from app.services.grading_extraction import CustomerDayCandidate, CustomerDayTranscript
from app.services.grading_pipeline import (
    GradeCustomerDayFailure,
    GradeCustomerDayFailureCode,
    GradeCustomerDaySuccess,
)


def _settings(**overrides) -> Settings:
    defaults = {
        "database_url": "sqlite:///tests.db",
        "auth_jwt_secret": "x" * 32,
        "auth_jwt_algorithm": "HS256",
        "auth_access_token_expire_minutes": 60,
        "grading_provider": "mock",
        "grading_model": GRADING_DEFAULT_MODEL,
        "grading_request_timeout_seconds": 5,
        "grading_max_retries": 1,
        "grading_prompt_version": GRADING_DEFAULT_PROMPT_VERSION,
        "grading_batch_max_backfill_days": 31,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _candidate(
    conversation_identity: str,
    *,
    grade_date: date = date(2026, 3, 5),
) -> CustomerDayCandidate:
    return CustomerDayCandidate(
        identity_type=IdentityType.PHONE,
        conversation_identity=conversation_identity,
        grade_date=grade_date,
    )


def _grading_output() -> GradingOutput:
    return GradingOutput(
        relevancy_score=8,
        relevancy_reasoning="Good",
        accuracy_score=8,
        accuracy_reasoning="Good",
        completeness_score=7,
        completeness_reasoning="Good",
        clarity_score=8,
        clarity_reasoning="Good",
        tone_score=9,
        tone_reasoning="Good",
        resolution=True,
        resolution_reasoning="Resolved",
        repetition_score=8,
        repetition_reasoning="Good",
        loop_detected=False,
        loop_detected_reasoning="No loop",
        satisfaction_score=8,
        satisfaction_reasoning="Good",
        frustration_score=2,
        frustration_reasoning="Good",
        user_relevancy=True,
        user_relevancy_reasoning="Relevant",
        escalation_occurred=False,
        escalation_occurred_reasoning="No escalation",
        escalation_type=EscalationType.NONE,
        escalation_type_reasoning="No escalation",
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        intent_reasoning="Intent identified",
    )


def _success_result(candidate: CustomerDayCandidate) -> GradeCustomerDaySuccess:
    transcript = CustomerDayTranscript(candidate=candidate, messages=())
    return GradeCustomerDaySuccess(
        candidate=candidate,
        transcript=transcript,
        prompt_plan=type("PromptPlan", (), {"bundles": ()})(),
        raw_outputs=(),
        output=_grading_output(),
    )


async def _persist_existing_grade(
    db_session,
    candidate: CustomerDayCandidate,
) -> None:
    db_session.add(
        ConversationGrade(
            identity_type=candidate.identity_type.value,
            conversation_identity=candidate.conversation_identity,
            phone_number=candidate.conversation_identity,
            grade_date=candidate.grade_date,
            intent_code="policy_inquiry",
            intent_label="Policy Inquiry",
            relevancy_score=7,
        )
    )
    await db_session.flush()


async def _persist_requesting_account(db_session) -> Account:
    account = Account(
        email="super-admin@example.com",
        password_hash="hashed-password",
        full_name="Super Admin",
        role="super_admin",
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    return account


async def _run_items_for_run(
    db_session,
    run_id,
) -> list[GradingRunItem]:
    result = await db_session.execute(
        select(GradingRunItem)
        .where(GradingRunItem.run_id == run_id)
        .order_by(GradingRunItem.conversation_identity)
    )
    return list(result.scalars().all())


def test_get_previous_gst_business_day_returns_weekday():
    result = get_previous_gst_business_day()
    assert isinstance(result, date)
    assert result.weekday() < 5


def test_plan_scheduled_batch_window_returns_single_day_window():
    window = plan_scheduled_batch_window()
    assert isinstance(window, GradingBatchWindow)
    assert window.start_date == window.end_date


def test_plan_manual_batch_window_rejects_inverted_range():
    request = type(
        "Request",
        (),
        {
            "grade_date": None,
            "target_start_date": date(2026, 3, 15),
            "target_end_date": date(2026, 3, 10),
            "rerun_existing": False,
        },
    )()

    with pytest.raises(ValueError, match="must be less than or equal"):
        plan_manual_batch_window(request, _settings())


def test_plan_manual_batch_window_rejects_span_exceeding_max_backfill():
    settings = _settings(grading_batch_max_backfill_days=7)
    request = type(
        "Request",
        (),
        {
            "grade_date": None,
            "target_start_date": date(2026, 1, 1),
            "target_end_date": date(2026, 1, 15),
            "rerun_existing": False,
        },
    )()

    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        plan_manual_batch_window(request, settings)


def test_plan_manual_batch_window_accepts_valid_range():
    request = type(
        "Request",
        (),
        {
            "grade_date": None,
            "target_start_date": date(2026, 3, 1),
            "target_end_date": date(2026, 3, 5),
            "rerun_existing": False,
        },
    )()

    window = plan_manual_batch_window(request, _settings())
    assert window.start_date == date(2026, 3, 1)
    assert window.end_date == date(2026, 3, 5)


def test_plan_manual_batch_window_rejects_exactly_max_inclusive_span():
    settings = _settings(grading_batch_max_backfill_days=7)
    request = type(
        "Request",
        (),
        {
            "grade_date": None,
            "target_start_date": date(2026, 1, 1),
            "target_end_date": date(2026, 1, 8),
            "rerun_existing": False,
        },
    )()

    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        plan_manual_batch_window(request, settings)


def test_plan_manual_batch_window_accepts_single_grade_date():
    request = type(
        "Request",
        (),
        {
            "grade_date": date(2026, 3, 5),
            "target_start_date": date(2026, 3, 5),
            "target_end_date": date(2026, 3, 5),
            "rerun_existing": False,
        },
    )()

    window = plan_manual_batch_window(request, _settings())
    assert window.start_date == date(2026, 3, 5)
    assert window.end_date == date(2026, 3, 5)


def test_compute_advisory_lock_key_deterministic():
    key1 = compute_advisory_lock_key(date(2026, 3, 5), date(2026, 3, 5))
    key2 = compute_advisory_lock_key(date(2026, 3, 5), date(2026, 3, 5))
    assert key1 == key2


def test_compute_advisory_lock_key_different_windows():
    key1 = compute_advisory_lock_key(date(2026, 3, 5), date(2026, 3, 5))
    key2 = compute_advisory_lock_key(date(2026, 3, 6), date(2026, 3, 6))
    assert key1 != key2


def test_compute_advisory_lock_key_is_deterministic_across_invocations():
    results = [
        compute_advisory_lock_key(date(2026, 3, 5), date(2026, 3, 5)) for _ in range(10)
    ]
    assert len(set(results)) == 1


@pytest.mark.asyncio
async def test_plan_batch_candidates_rerun_existing_includes_all(db_session):
    window = GradingBatchWindow(start_date=date(2026, 3, 5), end_date=date(2026, 3, 5))
    candidates = [
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000001",
            grade_date=date(2026, 3, 5),
        ),
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000002",
            grade_date=date(2026, 3, 5),
        ),
    ]

    with patch(
        "app.services.grading_extraction.list_customer_day_candidates",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = candidates
        plan = await plan_batch_candidates(db_session, window, rerun_existing=True)

    assert plan.rerun_existing is True
    assert len(plan.candidates) == 2


@pytest.mark.asyncio
async def test_plan_batch_candidates_skips_existing_grades(db_session):
    from app.models.conversation_grades import ConversationGrade
    from sqlalchemy import select

    window = GradingBatchWindow(start_date=date(2026, 3, 5), end_date=date(2026, 3, 5))
    candidates = [
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000001",
            grade_date=date(2026, 3, 5),
        ),
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000002",
            grade_date=date(2026, 3, 5),
        ),
    ]

    existing_grade = ConversationGrade(
        identity_type=IdentityType.PHONE.value,
        conversation_identity="+971500000001",
        phone_number="+971500000001",
        grade_date=date(2026, 3, 5),
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        relevancy_score=7,
    )
    db_session.add(existing_grade)
    await db_session.flush()

    with patch(
        "app.services.grading_extraction.list_customer_day_candidates",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = candidates
        plan = await plan_batch_candidates(db_session, window, rerun_existing=False)

    assert plan.rerun_existing is False
    assert len(plan.candidates) == 1
    assert plan.candidates[0].conversation_identity == "+971500000002"


@pytest.mark.asyncio
async def test_check_existing_grades_returns_existing_keys(db_session):
    from app.models.conversation_grades import ConversationGrade

    grade = ConversationGrade(
        identity_type=IdentityType.PHONE.value,
        conversation_identity="+971500000001",
        phone_number="+971500000001",
        grade_date=date(2026, 3, 5),
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        relevancy_score=7,
    )
    db_session.add(grade)
    await db_session.flush()

    candidates = [
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000001",
            grade_date=date(2026, 3, 5),
        ),
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000002",
            grade_date=date(2026, 3, 5),
        ),
    ]

    existing_keys = await check_existing_grades(db_session, candidates)

    assert ("phone", "+971500000001", date(2026, 3, 5)) in existing_keys
    assert ("phone", "+971500000002", date(2026, 3, 5)) not in existing_keys


@pytest.mark.asyncio
async def test_check_existing_grades_empty_for_no_candidates(db_session):
    existing_keys = await check_existing_grades(db_session, [])
    assert existing_keys == set()


def test_build_manual_batch_execution_request_backfill_mode():
    from app.services.grading_batch import build_manual_batch_execution_request
    from uuid import uuid4

    request = type(
        "Request",
        (),
        {
            "target_start_date": date(2026, 3, 5),
            "target_end_date": date(2026, 3, 5),
            "rerun_existing": False,
        },
    )()

    account_id = uuid4()

    execution_request = build_manual_batch_execution_request(
        request,
        requested_by_account_id=account_id,
    )

    assert execution_request.run_mode == GradingRunModeSchema.BACKFILL
    assert execution_request.rerun_existing is False
    assert execution_request.trigger_type == GradingRunTriggerTypeSchema.MANUAL


def test_build_manual_batch_execution_request_rerun_mode():
    from app.services.grading_batch import build_manual_batch_execution_request
    from uuid import uuid4

    request = type(
        "Request",
        (),
        {
            "target_start_date": date(2026, 3, 5),
            "target_end_date": date(2026, 3, 5),
            "rerun_existing": True,
        },
    )()

    account_id = uuid4()

    execution_request = build_manual_batch_execution_request(
        request,
        requested_by_account_id=account_id,
    )

    assert execution_request.run_mode == GradingRunModeSchema.RERUN
    assert execution_request.rerun_existing is True
    assert execution_request.trigger_type == GradingRunTriggerTypeSchema.MANUAL


@pytest.mark.asyncio
async def test_plan_batch_candidates_includes_skipped_candidates(db_session):
    from app.models.conversation_grades import ConversationGrade

    window = GradingBatchWindow(start_date=date(2026, 3, 5), end_date=date(2026, 3, 5))
    candidates = [
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000001",
            grade_date=date(2026, 3, 5),
        ),
        CustomerDayCandidate(
            identity_type=IdentityType.PHONE,
            conversation_identity="+971500000002",
            grade_date=date(2026, 3, 5),
        ),
    ]

    existing_grade = ConversationGrade(
        identity_type=IdentityType.PHONE.value,
        conversation_identity="+971500000001",
        phone_number="+971500000001",
        grade_date=date(2026, 3, 5),
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        relevancy_score=7,
    )
    db_session.add(existing_grade)
    await db_session.flush()

    with patch(
        "app.services.grading_extraction.list_customer_day_candidates",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = candidates
        plan = await plan_batch_candidates(db_session, window, rerun_existing=False)

    assert plan.rerun_existing is False
    assert len(plan.candidates) == 1
    assert plan.candidates[0].conversation_identity == "+971500000002"
    assert len(plan.skipped_candidates) == 1
    assert plan.skipped_candidates[0].conversation_identity == "+971500000001"
    assert plan.candidate_count == 1
    assert plan.skipped_candidate_count == 1


@pytest.mark.asyncio
async def test_grading_batch_runner_records_skipped_existing_items(db_session):
    from app.models.conversation_grades import ConversationGrade
    from app.models.grading_runs import GradingRun
    from app.schemas.grading_runs import GradingRunItemStatusSchema
    from app.services.grading_batch import GradingBatchPlan, GradingBatchRunner
    from app.services.grading_runs import SqlAlchemyGradingRunStore

    existing_grade = ConversationGrade(
        identity_type=IdentityType.PHONE.value,
        conversation_identity="+971500000001",
        phone_number="+971500000001",
        grade_date=date(2026, 3, 5),
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        relevancy_score=7,
    )
    db_session.add(existing_grade)
    await db_session.flush()

    run = GradingRun(
        trigger_type="manual",
        run_mode="backfill",
        status="queued",
        target_start_date=date(2026, 3, 5),
        target_end_date=date(2026, 3, 5),
        rerun_existing=False,
        provider="mock",
        model="gpt-4o",
        prompt_version="v1",
    )
    db_session.add(run)
    await db_session.flush()

    skipped_candidate = CustomerDayCandidate(
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500000001",
        grade_date=date(2026, 3, 5),
    )

    plan = GradingBatchPlan(
        window=GradingBatchWindow(date(2026, 3, 5), date(2026, 3, 5)),
        candidates=(),
        skipped_candidates=(skipped_candidate,),
        rerun_existing=False,
    )

    async def mock_grader(session, candidate):
        from app.services.grading_pipeline import (
            GradeCustomerDayFailure,
            GradeCustomerDayFailureCode,
        )

        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT,
            message="No messages",
            transcript=type("Transcript", (), {"messages": ()})(),
        )

    store = SqlAlchemyGradingRunStore()
    runner = GradingBatchRunner(db_session, mock_grader, store)

    await runner.execute_run(run, plan)

    await db_session.refresh(run)

    assert run.status == "completed"
    assert run.candidate_count == 1
    assert run.skipped_existing_count == 1
    assert run.attempted_count == 0
    assert run.success_count == 0


@pytest.mark.asyncio
async def test_grading_batch_runner_records_mixed_results(db_session):
    from app.models.grading_runs import GradingRun
    from app.schemas.grading_runs import GradingRunItemStatusSchema
    from app.services.grading_batch import GradingBatchPlan, GradingBatchRunner
    from app.services.grading_pipeline import (
        GradeCustomerDayFailure,
        GradeCustomerDayFailureCode,
    )
    from app.services.grading_runs import SqlAlchemyGradingRunStore

    run = GradingRun(
        trigger_type="manual",
        run_mode="backfill",
        status="queued",
        target_start_date=date(2026, 3, 5),
        target_end_date=date(2026, 3, 5),
        rerun_existing=False,
        provider="mock",
        model="gpt-4o",
        prompt_version="v1",
    )
    db_session.add(run)
    await db_session.flush()

    candidate1 = CustomerDayCandidate(
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500000001",
        grade_date=date(2026, 3, 5),
    )
    candidate2 = CustomerDayCandidate(
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500000002",
        grade_date=date(2026, 3, 5),
    )
    candidate3 = CustomerDayCandidate(
        identity_type=IdentityType.PHONE,
        conversation_identity="+971500000003",
        grade_date=date(2026, 3, 5),
    )

    plan = GradingBatchPlan(
        window=GradingBatchWindow(date(2026, 3, 5), date(2026, 3, 5)),
        candidates=(candidate1, candidate2, candidate3),
        skipped_candidates=(),
        rerun_existing=False,
    )

    from app.services.grading_extraction import CustomerDayTranscript
    from app.schemas.grading import GradingOutput, EscalationType

    transcript1 = CustomerDayTranscript(candidate=candidate1, messages=())
    transcript2 = CustomerDayTranscript(candidate=candidate2, messages=())
    transcript3 = CustomerDayTranscript(candidate=candidate3, messages=())

    success_output = GradingOutput(
        relevancy_score=8,
        relevancy_reasoning="Good",
        accuracy_score=8,
        accuracy_reasoning="Good",
        completeness_score=7,
        completeness_reasoning="Good",
        clarity_score=8,
        clarity_reasoning="Good",
        tone_score=9,
        tone_reasoning="Good",
        resolution=True,
        resolution_reasoning="Resolved",
        repetition_score=8,
        repetition_reasoning="Good",
        loop_detected=False,
        loop_detected_reasoning="No loop",
        satisfaction_score=8,
        satisfaction_reasoning="Good",
        frustration_score=2,
        frustration_reasoning="Good",
        user_relevancy=True,
        user_relevancy_reasoning="Relevant",
        escalation_occurred=False,
        escalation_occurred_reasoning="No escalation",
        escalation_type=EscalationType.NONE,
        escalation_type_reasoning="No escalation",
        intent_code="policy_inquiry",
        intent_label="Policy Inquiry",
        intent_reasoning="Intent identified",
    )

    async def mock_grader(session, candidate):
        if candidate.conversation_identity == "+971500000001":
            success_result = GradeCustomerDaySuccess(
                candidate=candidate,
                transcript=transcript1,
                prompt_plan=type("Plan", (), {"bundles": ()})(),
                raw_outputs=(),
                output=success_output,
            )
            return success_result
        elif candidate.conversation_identity == "+971500000002":
            return GradeCustomerDayFailure(
                candidate=candidate,
                code=GradeCustomerDayFailureCode.PROVIDER_ERROR,
                message="Provider failed",
                transcript=transcript2,
            )
        else:
            return GradeCustomerDayFailure(
                candidate=candidate,
                code=GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT,
                message="No messages",
                transcript=transcript3,
            )

    store = SqlAlchemyGradingRunStore()
    runner = GradingBatchRunner(db_session, mock_grader, store)

    await runner.execute_run(run, plan)

    await db_session.refresh(run)

    assert run.status == "completed_with_failures"
    assert run.candidate_count == 3
    assert run.attempted_count == 3
    assert run.success_count == 1
    assert run.provider_error_count == 1
    assert run.empty_transcript_count == 1


@pytest.mark.asyncio
async def test_execute_grading_batch_fails_for_duplicate_active_window(db_session):
    duplicate_run = GradingRun(
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED.value,
        run_mode=GradingRunModeSchema.DAILY.value,
        status=GradingRunStatusSchema.RUNNING.value,
        target_start_date=date(2026, 3, 5),
        target_end_date=date(2026, 3, 5),
        rerun_existing=False,
        provider="mock",
        model=GRADING_DEFAULT_MODEL,
        prompt_version=GRADING_DEFAULT_PROMPT_VERSION,
    )
    db_session.add(duplicate_run)
    await db_session.flush()

    grader = AsyncMock()
    request = GradingBatchExecutionRequest(
        window=GradingBatchWindow(date(2026, 3, 5), date(2026, 3, 5)),
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED,
        run_mode=GradingRunModeSchema.DAILY,
        rerun_existing=False,
    )

    run = await execute_grading_batch(
        db_session,
        request,
        grader,
        settings=_settings(),
    )

    persisted_items = await _run_items_for_run(db_session, run.id)

    assert grader.await_count == 0
    assert run.status == GradingRunStatusSchema.FAILED.value
    assert run.started_at is None
    assert run.finished_at is not None
    assert "already active" in (run.error_message or "")
    assert run.target_start_date == date(2026, 3, 5)
    assert run.target_end_date == date(2026, 3, 5)
    assert persisted_items == []


@pytest.mark.asyncio
async def test_execute_grading_batch_fails_when_advisory_lock_is_unavailable(
    db_session,
):
    grader = AsyncMock()
    request = GradingBatchExecutionRequest(
        window=GradingBatchWindow(date(2026, 3, 5), date(2026, 3, 5)),
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED,
        run_mode=GradingRunModeSchema.DAILY,
        rerun_existing=False,
    )

    with patch(
        "app.services.grading_batch.acquire_advisory_lock",
        new_callable=AsyncMock,
    ) as mock_acquire_lock:
        mock_acquire_lock.return_value = False
        run = await execute_grading_batch(
            db_session,
            request,
            grader,
            settings=_settings(),
        )

    persisted_items = await _run_items_for_run(db_session, run.id)

    assert mock_acquire_lock.await_count == 1
    assert grader.await_count == 0
    assert run.status == GradingRunStatusSchema.FAILED.value
    assert run.started_at is None
    assert run.finished_at is not None
    assert "Could not acquire advisory lock" in (run.error_message or "")
    assert persisted_items == []


@pytest.mark.asyncio
async def test_execute_grading_batch_persists_failed_status_after_running_exception(
    db_session,
):
    candidate = _candidate("+971500000099")
    grader = AsyncMock(side_effect=RuntimeError("grader crashed after start"))
    request = GradingBatchExecutionRequest(
        window=GradingBatchWindow(date(2026, 3, 5), date(2026, 3, 5)),
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED,
        run_mode=GradingRunModeSchema.DAILY,
        rerun_existing=False,
    )

    with patch(
        "app.services.grading_batch.acquire_advisory_lock",
        new_callable=AsyncMock,
    ) as mock_acquire_lock:
        with patch(
            "app.services.grading_extraction.list_customer_day_candidates",
            new_callable=AsyncMock,
        ) as mock_list_candidates:
            mock_acquire_lock.return_value = True
            mock_list_candidates.return_value = [candidate]
            run = await execute_grading_batch(
                db_session,
                request,
                grader,
                settings=_settings(),
            )

    await db_session.rollback()
    await db_session.refresh(run)
    persisted_items = await _run_items_for_run(db_session, run.id)

    assert mock_acquire_lock.await_count == 1
    assert grader.await_count == 1
    assert run.status == GradingRunStatusSchema.FAILED.value
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.error_message == "grader crashed after start"
    assert persisted_items == []


@pytest.mark.asyncio
async def test_execute_grading_batch_records_scheduled_mixed_outcomes(
    db_session,
):
    skipped_candidate = _candidate("+971500000001")
    success_candidate = _candidate("+971500000002")
    provider_error_candidate = _candidate("+971500000003")
    await _persist_existing_grade(db_session, skipped_candidate)

    grader_calls: list[str] = []

    async def mock_grader(session, candidate):
        grader_calls.append(candidate.conversation_identity)
        if candidate.conversation_identity == success_candidate.conversation_identity:
            return _success_result(candidate)
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.PROVIDER_ERROR,
            message="Provider failed",
            transcript=CustomerDayTranscript(candidate=candidate, messages=()),
            details=("provider timeout",),
        )

    request = GradingBatchExecutionRequest(
        window=GradingBatchWindow(date(2026, 3, 5), date(2026, 3, 5)),
        trigger_type=GradingRunTriggerTypeSchema.SCHEDULED,
        run_mode=GradingRunModeSchema.DAILY,
        rerun_existing=False,
    )

    with patch(
        "app.services.grading_extraction.list_customer_day_candidates",
        new_callable=AsyncMock,
    ) as mock_list_candidates:
        mock_list_candidates.return_value = [
            skipped_candidate,
            success_candidate,
            provider_error_candidate,
        ]
        run = await execute_grading_batch(
            db_session,
            request,
            mock_grader,
            settings=_settings(),
        )

    persisted_items = await _run_items_for_run(db_session, run.id)

    assert grader_calls == [
        success_candidate.conversation_identity,
        provider_error_candidate.conversation_identity,
    ]
    assert run.trigger_type == GradingRunTriggerTypeSchema.SCHEDULED.value
    assert run.run_mode == GradingRunModeSchema.DAILY.value
    assert run.status == GradingRunStatusSchema.COMPLETED_WITH_FAILURES.value
    assert run.candidate_count == 3
    assert run.attempted_count == 2
    assert run.success_count == 1
    assert run.skipped_existing_count == 1
    assert run.provider_error_count == 1
    assert run.parse_error_count == 0
    assert run.started_at is not None
    assert run.finished_at is not None
    assert {
        item.conversation_identity: item.status for item in persisted_items
    } == {
        skipped_candidate.conversation_identity: GradingRunItemStatusSchema.SKIPPED_EXISTING.value,
        success_candidate.conversation_identity: GradingRunItemStatusSchema.SUCCESS.value,
        provider_error_candidate.conversation_identity: GradingRunItemStatusSchema.PROVIDER_ERROR.value,
    }


@pytest.mark.asyncio
async def test_execute_grading_batch_manual_rerun_reprocesses_existing_grade(
    db_session,
):
    candidate = _candidate("+971500000004")
    await _persist_existing_grade(db_session, candidate)
    account = await _persist_requesting_account(db_session)

    grader_calls: list[str] = []

    async def mock_grader(session, graded_candidate):
        grader_calls.append(graded_candidate.conversation_identity)
        return _success_result(graded_candidate)

    trigger_request = GradingRunTriggerRequest(
        grade_date=candidate.grade_date,
        rerun_existing=True,
    )
    request = build_manual_batch_execution_request(
        trigger_request,
        requested_by_account_id=account.id,
    )

    with patch(
        "app.services.grading_extraction.list_customer_day_candidates",
        new_callable=AsyncMock,
    ) as mock_list_candidates:
        mock_list_candidates.return_value = [candidate]
        run = await execute_grading_batch(
            db_session,
            request,
            mock_grader,
            settings=_settings(),
        )

    persisted_items = await _run_items_for_run(db_session, run.id)

    assert grader_calls == [candidate.conversation_identity]
    assert run.trigger_type == GradingRunTriggerTypeSchema.MANUAL.value
    assert run.run_mode == GradingRunModeSchema.RERUN.value
    assert run.rerun_existing is True
    assert run.requested_by_account_id == account.id
    assert run.status == GradingRunStatusSchema.COMPLETED.value
    assert run.candidate_count == 1
    assert run.attempted_count == 1
    assert run.success_count == 1
    assert run.skipped_existing_count == 0
    assert len(persisted_items) == 1
    assert persisted_items[0].status == GradingRunItemStatusSchema.SUCCESS.value
    assert persisted_items[0].conversation_identity == candidate.conversation_identity
