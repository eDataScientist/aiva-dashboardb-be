from __future__ import annotations

from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_grades import ConversationGrade
from app.models.enums import IdentityType
from app.schemas.grading import GradingOutput
from app.services.grading_extraction import CustomerDayCandidate


class GradingPersistence(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        candidate: CustomerDayCandidate,
        output: GradingOutput,
    ) -> None: ...


async def upsert_customer_day_grade(
    session: AsyncSession,
    candidate: CustomerDayCandidate,
    output: GradingOutput,
) -> None:
    grade = await _find_existing_grade(session, candidate)
    values = _build_grade_values(candidate, output)

    if grade is None:
        session.add(ConversationGrade(**values))
    else:
        for field_name, value in values.items():
            setattr(grade, field_name, value)

    await session.flush()


async def _find_existing_grade(
    session: AsyncSession,
    candidate: CustomerDayCandidate,
) -> ConversationGrade | None:
    stmt = select(ConversationGrade).where(ConversationGrade.grade_date == candidate.grade_date)

    if candidate.identity_type == IdentityType.PHONE:
        stmt = stmt.where(
            or_(
                (
                    ConversationGrade.identity_type == IdentityType.PHONE.value
                )
                & (
                    ConversationGrade.conversation_identity
                    == candidate.conversation_identity
                ),
                ConversationGrade.phone_number == candidate.conversation_identity,
            )
        )
    else:
        stmt = stmt.where(
            ConversationGrade.identity_type == candidate.identity_type.value,
            ConversationGrade.conversation_identity == candidate.conversation_identity,
        )

    return await session.scalar(stmt.limit(1))


def _build_grade_values(
    candidate: CustomerDayCandidate,
    output: GradingOutput,
) -> dict[str, object]:
    values = output.model_dump(mode="json")
    values.update(
        {
            "phone_number": _phone_number_for_candidate(candidate),
            "identity_type": candidate.identity_type.value,
            "conversation_identity": candidate.conversation_identity,
            "grade_date": candidate.grade_date,
        }
    )
    return values


def _phone_number_for_candidate(candidate: CustomerDayCandidate) -> str | None:
    if candidate.identity_type == IdentityType.PHONE:
        return candidate.conversation_identity
    return None
