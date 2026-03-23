from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from app.core.config import Settings, get_settings
from app.schemas.grading import GradingOutput, GradingParseError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.grading_extraction import (
    CustomerDayCandidate,
    CustomerDayTranscript,
    MINIMUM_HUMAN_MESSAGES_FOR_GRADING,
    assemble_customer_day_transcript,
)
from app.services.grading_parser import GradingParseFailure, PromptExecutionParser
from app.services.grading_persistence import GradingPersistence
from app.services.grading_prompt import (
    MultiPromptExecutionPlanner,
    PromptBundle,
    PromptExecutionPlan,
)
from app.services.grading_provider import (
    GradingProvider,
    GradingProviderError,
    GradingProviderRequest,
)


@dataclass(frozen=True, slots=True)
class GradingPipelineDependencies:
    settings: Settings
    prompt_planner: MultiPromptExecutionPlanner
    provider: GradingProvider
    parser: PromptExecutionParser
    persistence: GradingPersistence


class GradeCustomerDayFailureCode(str, Enum):
    EMPTY_TRANSCRIPT = "empty_transcript"
    PROVIDER_ERROR = "provider_error"
    PARSE_ERROR = "parse_error"


@dataclass(frozen=True, slots=True)
class GradeCustomerDaySuccess:
    candidate: CustomerDayCandidate
    transcript: CustomerDayTranscript
    prompt_plan: PromptExecutionPlan
    raw_outputs: tuple[tuple[PromptBundle, str], ...]
    output: GradingOutput

    @property
    def ok(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class GradeCustomerDayFailure:
    candidate: CustomerDayCandidate
    code: GradeCustomerDayFailureCode
    message: str
    transcript: CustomerDayTranscript
    details: tuple[str, ...] = ()
    prompt_plan: PromptExecutionPlan | None = None
    raw_outputs: tuple[tuple[PromptBundle, str], ...] = ()
    parse_error: GradingParseError | None = None

    @property
    def ok(self) -> bool:
        return False


GradeCustomerDayResult = GradeCustomerDaySuccess | GradeCustomerDayFailure


@dataclass(frozen=True, slots=True)
class _PromptExecutionProviderFailure(Exception):
    error: GradingProviderError
    raw_outputs: tuple[tuple[PromptBundle, str], ...]
    details: tuple[str, ...]


async def grade_customer_day(
    session: AsyncSession,
    candidate: CustomerDayCandidate,
    dependencies: GradingPipelineDependencies,
) -> GradeCustomerDayResult:
    transcript = await assemble_customer_day_transcript(session, candidate)
    if not transcript.messages:
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT,
            message="No transcript messages were found for the requested customer-day.",
            transcript=transcript,
        )
    if transcript.human_message_count < MINIMUM_HUMAN_MESSAGES_FOR_GRADING:
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.EMPTY_TRANSCRIPT,
            message=(
                "Customer-day transcript must include at least "
                f"{MINIMUM_HUMAN_MESSAGES_FOR_GRADING} inbound human messages before grading."
            ),
            transcript=transcript,
        )

    prompt_plan = dependencies.prompt_planner(transcript)

    try:
        raw_outputs = await _execute_prompt_plan(
            prompt_plan=prompt_plan,
            dependencies=dependencies,
        )
    except _PromptExecutionProviderFailure as exc:
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.PROVIDER_ERROR,
            message=str(exc.error),
            transcript=transcript,
            details=exc.details,
            prompt_plan=prompt_plan,
            raw_outputs=exc.raw_outputs,
        )

    try:
        parsed = dependencies.parser(raw_outputs)
    except GradingParseFailure as exc:
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.PARSE_ERROR,
            message=exc.error.message,
            transcript=transcript,
            details=tuple(exc.error.details),
            prompt_plan=prompt_plan,
            raw_outputs=raw_outputs,
            parse_error=exc.error,
        )

    await dependencies.persistence(session, candidate, parsed.output)

    return GradeCustomerDaySuccess(
        candidate=candidate,
        transcript=transcript,
        prompt_plan=prompt_plan,
        raw_outputs=raw_outputs,
        output=parsed.output,
    )


def build_grading_pipeline_dependencies(
    *,
    settings: Settings | None = None,
    prompt_planner: MultiPromptExecutionPlanner,
    provider: GradingProvider,
    parser: PromptExecutionParser,
    persistence: GradingPersistence,
) -> GradingPipelineDependencies:
    return GradingPipelineDependencies(
        settings=settings or get_settings(),
        prompt_planner=prompt_planner,
        provider=provider,
        parser=parser,
        persistence=persistence,
    )


async def _execute_prompt_plan(
    *,
    prompt_plan: PromptExecutionPlan,
    dependencies: GradingPipelineDependencies,
) -> tuple[tuple[PromptBundle, str], ...]:
    executions = await asyncio.gather(
        *(
            _execute_prompt_bundle(
                bundle=bundle,
                dependencies=dependencies,
            )
            for bundle in prompt_plan.bundles
        ),
        return_exceptions=True,
    )

    raw_outputs: list[tuple[PromptBundle, str]] = []
    provider_errors: list[tuple[PromptBundle, GradingProviderError]] = []
    for bundle, execution in zip(prompt_plan.bundles, executions):
        if isinstance(execution, Exception):
            if isinstance(execution, GradingProviderError):
                error = execution
            else:
                error = GradingProviderError(str(execution))
            provider_errors.append((bundle, error))
            continue
        raw_outputs.append(execution)

    if provider_errors:
        raise _PromptExecutionProviderFailure(
            error=provider_errors[0][1],
            raw_outputs=tuple(raw_outputs),
            details=tuple(
                f"{bundle.prompt_key}: {error}"
                for bundle, error in provider_errors
            ),
        )

    return tuple(raw_outputs)


async def _execute_prompt_bundle(
    *,
    bundle: PromptBundle,
    dependencies: GradingPipelineDependencies,
) -> tuple[PromptBundle, str]:
    raw_output = await dependencies.provider(
        GradingProviderRequest(
            prompt=bundle,
            model=dependencies.settings.grading_model,
            timeout_seconds=dependencies.settings.grading_request_timeout_seconds,
            max_retries=dependencies.settings.grading_max_retries,
        )
    )
    return bundle, raw_output
