from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Select, select

from app.models.conversation_grades import ConversationGrade
from app.models.enums import normalize_identity_type


@dataclass(frozen=True, slots=True)
class MonitoringDateWindow:
    start_date: date
    end_date: date


def build_monitoring_list_stmt(
    window: MonitoringDateWindow,
) -> Select[tuple[ConversationGrade]]:
    return (
        select(ConversationGrade)
        .where(ConversationGrade.grade_date >= window.start_date)
        .where(ConversationGrade.grade_date <= window.end_date)
    )


def build_monitoring_detail_stmt(grade_id: Any) -> Select[tuple[ConversationGrade]]:
    return select(ConversationGrade).where(ConversationGrade.id == grade_id)


def build_monitoring_history_stmt(
    *,
    identity_type: str,
    conversation_identity: str,
) -> Select[tuple[ConversationGrade]]:
    return (
        select(ConversationGrade)
        .where(ConversationGrade.identity_type == identity_type)
        .where(ConversationGrade.conversation_identity == conversation_identity)
        .order_by(ConversationGrade.grade_date.desc(), ConversationGrade.id.desc())
    )


def build_monitoring_same_day_messages_stmt(
    *,
    identity_type: str,
    conversation_identity: str,
    grade_date: date,
):
    from app.services.grading_extraction import (
        CustomerDayCandidate,
        build_customer_day_messages_stmt,
    )

    normalized_identity_type = normalize_identity_type(identity_type)
    if normalized_identity_type is None:
        raise ValueError("identity_type must be a supported canonical identity type.")

    return build_customer_day_messages_stmt(
        CustomerDayCandidate(
            identity_type=normalized_identity_type,
            conversation_identity=conversation_identity,
            grade_date=grade_date,
        )
    )
