from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.core.config import Settings, get_settings
from app.schemas.grading import GradingOutput, GradingParseError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.grading_extraction import (
    CustomerDayCandidate,
    CustomerDayTranscript,
    assemble_customer_day_transcript,
)
from app.services.grading_parser import GradingParseFailure, GradingParser
from app.services.grading_persistence import GradingPersistence
from app.services.grading_prompt import GradingPromptBuilder, PromptBundle
from app.services.grading_provider import (
    GradingProvider,
    GradingProviderError,
    GradingProviderRequest,
)


@dataclass(frozen=True, slots=True)
class GradingPipelineDependencies:
    settings: Settings
    prompt_builder: GradingPromptBuilder
    provider: GradingProvider
    parser: GradingParser
    persistence: GradingPersistence


class GradeCustomerDayFailureCode(str, Enum):
    EMPTY_TRANSCRIPT = "empty_transcript"
    PROVIDER_ERROR = "provider_error"
    PARSE_ERROR = "parse_error"


@dataclass(frozen=True, slots=True)
class GradeCustomerDaySuccess:
    candidate: CustomerDayCandidate
    transcript: CustomerDayTranscript
    prompt: PromptBundle
    raw_output: str
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
    prompt: PromptBundle | None = None
    raw_output: str | None = None
    parse_error: GradingParseError | None = None

    @property
    def ok(self) -> bool:
        return False


GradeCustomerDayResult = GradeCustomerDaySuccess | GradeCustomerDayFailure


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

    prompt = dependencies.prompt_builder(transcript)

    try:
        raw_output = await dependencies.provider(
            GradingProviderRequest(
                prompt=prompt,
                model=dependencies.settings.grading_model,
                timeout_seconds=dependencies.settings.grading_request_timeout_seconds,
                max_retries=dependencies.settings.grading_max_retries,
            )
        )
    except GradingProviderError as exc:
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.PROVIDER_ERROR,
            message=str(exc),
            transcript=transcript,
            prompt=prompt,
        )

    try:
        parsed = dependencies.parser(raw_output)
    except GradingParseFailure as exc:
        return GradeCustomerDayFailure(
            candidate=candidate,
            code=GradeCustomerDayFailureCode.PARSE_ERROR,
            message=exc.error.message,
            transcript=transcript,
            details=tuple(exc.error.details),
            prompt=prompt,
            raw_output=exc.error.raw_output,
            parse_error=exc.error,
        )

    await dependencies.persistence(session, candidate, parsed.output)

    return GradeCustomerDaySuccess(
        candidate=candidate,
        transcript=transcript,
        prompt=prompt,
        raw_output=raw_output,
        output=parsed.output,
    )


def build_grading_pipeline_dependencies(
    *,
    settings: Settings | None = None,
    prompt_builder: GradingPromptBuilder,
    provider: GradingProvider,
    parser: GradingParser,
    persistence: GradingPersistence,
) -> GradingPipelineDependencies:
    return GradingPipelineDependencies(
        settings=settings or get_settings(),
        prompt_builder=prompt_builder,
        provider=provider,
        parser=parser,
        persistence=persistence,
    )
