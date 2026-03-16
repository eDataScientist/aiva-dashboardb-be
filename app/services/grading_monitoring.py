from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, case, cast, func, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import INTENT_CODE_TO_CATEGORY, INTENT_CODE_TO_LABEL, get_settings
from app.models.chats import ChatMessage
from app.models.conversation_grades import ConversationGrade
from app.models.enums import normalize_identity_type
from app.schemas.grading_metrics import GradingMetricsFreshness
from app.schemas.grading_monitoring import (
    MonitoringConversationDetail,
    MonitoringConversationHistoryItem,
    MonitoringConversationListResponse,
    MonitoringConversationListQuery,
    MonitoringConversationSummary,
    MonitoringConversationTranscriptMessage,
    MonitoringGradePanel,
)
from app.services.conversations import encode_conversation_key
from app.services.grading_extraction import (
    CustomerDayCandidate,
    assemble_customer_day_transcript,
)
from app.services.grading_metrics import (
    get_latest_successful_grading_metrics_freshness,
)
from app.services.monitoring_highlights import (
    evaluate_monitoring_highlights,
    load_monitoring_highlight_rules,
)


@dataclass(frozen=True, slots=True)
class MonitoringDateWindow:
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class MonitoringConversationListRow:
    grade: ConversationGrade
    contact_name: str | None
    latest_message_preview: str | None
    latest_message_at: datetime | None
    message_count: int


@dataclass(frozen=True, slots=True)
class MonitoringConversationListPage:
    total: int
    items: list[MonitoringConversationListRow]


class MonitoringConversationNotFoundError(LookupError):
    """Raised when a monitoring detail row cannot be loaded cleanly."""


def build_monitoring_list_stmt(
    query: MonitoringConversationListQuery,
) -> Select[Any]:
    contact_name = _build_monitoring_contact_name_expr().label("contact_name")
    latest_message_preview = _build_monitoring_latest_message_preview_expr().label(
        "latest_message_preview"
    )
    latest_message_at = _build_monitoring_latest_message_at_expr().label(
        "latest_message_at"
    )
    message_count = _build_monitoring_message_count_expr().label("message_count")
    stmt = (
        select(
            ConversationGrade,
            contact_name,
            latest_message_preview,
            latest_message_at,
            message_count,
        )
        .where(_nullif_blank(ConversationGrade.identity_type).is_not(None))
        .where(_nullif_blank(ConversationGrade.conversation_identity).is_not(None))
        .where(ConversationGrade.grade_date >= query.start_date)
        .where(ConversationGrade.grade_date <= query.end_date)
    )
    stmt = _apply_monitoring_list_filters(stmt, query)
    return _apply_monitoring_list_ordering(stmt, query, latest_message_at)


async def list_monitoring_conversation_grades(
    session: AsyncSession,
    query: MonitoringConversationListQuery,
) -> MonitoringConversationListPage:
    stmt = build_monitoring_list_stmt(query)
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.scalar(total_stmt)) or 0)
    rows = (await session.execute(stmt.limit(query.limit).offset(query.offset))).all()

    return MonitoringConversationListPage(
        total=total,
        items=[
            MonitoringConversationListRow(
                grade=grade,
                contact_name=_strip_or_none(contact_name),
                latest_message_preview=_strip_or_none(latest_message_preview),
                latest_message_at=latest_message_at,
                message_count=int(message_count or 0),
            )
            for (
                grade,
                contact_name,
                latest_message_preview,
                latest_message_at,
                message_count,
            ) in rows
        ],
    )


async def get_monitoring_conversation_list(
    session: AsyncSession,
    query: MonitoringConversationListQuery,
) -> MonitoringConversationListResponse:
    rules = await load_monitoring_highlight_rules(session)
    page = await list_monitoring_conversation_grades(session, query)
    freshness_record = await get_latest_successful_grading_metrics_freshness(session)

    return MonitoringConversationListResponse(
        date_window=query.date_window,
        total=page.total,
        limit=query.limit,
        offset=query.offset,
        items=[
            MonitoringConversationSummary(
                grade_id=row.grade.id,
                grade_date=row.grade.grade_date,
                conversation_key=_resolve_monitoring_conversation_key(row.grade),
                contact_name=row.contact_name,
                latest_message_preview=row.latest_message_preview,
                latest_message_at=row.latest_message_at,
                message_count=row.message_count,
                intent_code=_resolve_intent_code(row.grade.intent_code),
                intent_label=_resolve_intent_label(row.grade.intent_code),
                intent_category=_resolve_intent_category(row.grade.intent_code),
                resolution=row.grade.resolution,
                escalation_type=row.grade.escalation_type,
                frustration_score=row.grade.frustration_score,
                accuracy_score=row.grade.accuracy_score,
                highlights=evaluate_monitoring_highlights(row.grade, rules),
            )
            for row in page.items
        ],
        freshness=GradingMetricsFreshness(
            latest_successful_run_id=(
                None if freshness_record is None else freshness_record.run_id
            ),
            latest_successful_window_end_date=(
                None if freshness_record is None else freshness_record.target_end_date
            ),
            latest_successful_run_finished_at=(
                None if freshness_record is None else freshness_record.finished_at
            ),
        ),
    )


async def get_monitoring_conversation_detail(
    session: AsyncSession,
    grade_id: Any,
    *,
    history_limit: int | None = None,
) -> MonitoringConversationDetail:
    grade = await session.scalar(build_monitoring_detail_stmt(grade_id))
    candidate = _to_customer_day_candidate(grade)
    if grade is None or candidate is None:
        raise MonitoringConversationNotFoundError("Grade not found.")

    transcript = await assemble_customer_day_transcript(session, candidate)
    if not transcript.messages:
        raise MonitoringConversationNotFoundError("Grade not found.")

    contact_name = await _load_monitoring_contact_name(
        session,
        identity_type=candidate.identity_type.value,
        conversation_identity=candidate.conversation_identity,
        grade_date=candidate.grade_date,
    )
    rules = await load_monitoring_highlight_rules(session)
    resolved_history_limit = (
        get_settings().monitoring_default_recent_history_limit
        if history_limit is None
        else max(history_limit, 0)
    )

    return MonitoringConversationDetail(
        grade_id=grade.id,
        grade_date=grade.grade_date,
        conversation_key=_resolve_monitoring_conversation_key(grade),
        contact_name=contact_name,
        latest_message_preview=transcript.messages[-1].normalized_content,
        latest_message_at=transcript.messages[-1].created_at,
        message_count=len(transcript.messages),
        intent_code=grade.intent_code,
        intent_label=grade.intent_label,
        intent_category=_resolve_intent_category(grade.intent_code),
        resolution=grade.resolution,
        escalation_type=grade.escalation_type,
        frustration_score=grade.frustration_score,
        accuracy_score=grade.accuracy_score,
        highlights=evaluate_monitoring_highlights(grade, rules),
        grade_panel=_build_monitoring_grade_panel(grade),
        transcript=[
            MonitoringConversationTranscriptMessage(
                role=_to_monitoring_transcript_role(message.direction),
                content=message.normalized_content,
                created_at=message.created_at,
            )
            for message in transcript.messages
        ],
        recent_history=await _load_monitoring_recent_history(
            session,
            grade=grade,
            rules=rules,
            history_limit=resolved_history_limit,
        ),
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


def _build_monitoring_latest_message_at_expr():
    return (
        select(ChatMessage.created_at)
        .where(*_build_monitoring_chat_match_filters())
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .correlate(ConversationGrade)
        .limit(1)
        .scalar_subquery()
    )


def _build_monitoring_contact_name_expr():
    contact_name_expr = _nullif_blank(ChatMessage.customer_name)
    return (
        select(contact_name_expr)
        .where(*_build_monitoring_chat_match_filters())
        .order_by(
            case((contact_name_expr.is_(None), 1), else_=0),
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .correlate(ConversationGrade)
        .limit(1)
        .scalar_subquery()
    )


def _build_monitoring_latest_message_preview_expr():
    return (
        select(ChatMessage.message)
        .where(*_build_monitoring_chat_match_filters())
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .correlate(ConversationGrade)
        .limit(1)
        .scalar_subquery()
    )


def _build_monitoring_message_count_expr():
    return (
        select(func.count(ChatMessage.id))
        .where(*_build_monitoring_chat_match_filters())
        .correlate(ConversationGrade)
        .scalar_subquery()
    )


def _build_monitoring_contact_name_stmt(
    *,
    identity_type: str,
    conversation_identity: str,
    grade_date: date,
):
    from app.services.grading_extraction import (
        canonical_identity_type_expr,
        canonical_identity_value_expr,
        gst_grade_date_expr,
    )

    contact_name_expr = func.nullif(
        func.btrim(cast(ChatMessage.customer_name, String())),
        "",
    )
    return (
        select(contact_name_expr)
        .where(canonical_identity_type_expr() == identity_type)
        .where(canonical_identity_value_expr() == conversation_identity)
        .where(gst_grade_date_expr() == grade_date)
        .order_by(
            case((contact_name_expr.is_(None), 1), else_=0),
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .limit(1)
    )


def _apply_monitoring_list_filters(
    stmt: Select[Any],
    query: MonitoringConversationListQuery,
) -> Select[Any]:
    if query.resolution is not None:
        stmt = stmt.where(ConversationGrade.resolution.is_(query.resolution))
    if query.escalation_types:
        stmt = stmt.where(
            ConversationGrade.escalation_type.in_(tuple(query.escalation_types))
        )
    if query.frustration_min is not None:
        stmt = stmt.where(
            ConversationGrade.frustration_score.is_not(None),
            ConversationGrade.frustration_score >= query.frustration_min,
        )
    if query.accuracy_max is not None:
        stmt = stmt.where(
            ConversationGrade.accuracy_score.is_not(None),
            ConversationGrade.accuracy_score <= query.accuracy_max,
        )
    if query.intent_codes:
        stmt = stmt.where(ConversationGrade.intent_code.in_(tuple(query.intent_codes)))
    return stmt


def _apply_monitoring_list_ordering(
    stmt: Select[Any],
    query: MonitoringConversationListQuery,
    latest_message_at: Any,
) -> Select[Any]:
    order_by_clauses: list[Any] = []
    if query.sort_by is not None:
        sort_column = getattr(ConversationGrade, query.sort_by)
        sort_clause = (
            sort_column.asc().nulls_last()
            if query.sort_direction == "asc"
            else sort_column.desc().nulls_last()
        )
        order_by_clauses.append(sort_clause)

    order_by_clauses.extend(
        (
            ConversationGrade.grade_date.desc(),
            latest_message_at.desc().nulls_last(),
            ConversationGrade.id.desc(),
        )
    )
    return stmt.order_by(*order_by_clauses)


def _to_customer_day_candidate(
    grade: ConversationGrade | None,
) -> CustomerDayCandidate | None:
    if grade is None:
        return None

    normalized_identity_type = normalize_identity_type(grade.identity_type)
    conversation_identity = (grade.conversation_identity or "").strip()
    if normalized_identity_type is None or not conversation_identity:
        return None

    return CustomerDayCandidate(
        identity_type=normalized_identity_type,
        conversation_identity=conversation_identity,
        grade_date=grade.grade_date,
    )


async def _load_monitoring_contact_name(
    session: AsyncSession,
    *,
    identity_type: str,
    conversation_identity: str,
    grade_date: date,
) -> str | None:
    value = await session.scalar(
        _build_monitoring_contact_name_stmt(
            identity_type=identity_type,
            conversation_identity=conversation_identity,
            grade_date=grade_date,
        )
    )
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


async def _load_monitoring_recent_history(
    session: AsyncSession,
    *,
    grade: ConversationGrade,
    rules: Any,
    history_limit: int,
) -> list[MonitoringConversationHistoryItem]:
    if history_limit <= 0:
        return []

    identity_type = _strip_or_none(grade.identity_type)
    conversation_identity = _strip_or_none(grade.conversation_identity)
    if identity_type is None or conversation_identity is None:
        return []

    rows = (
        await session.scalars(
            build_monitoring_history_stmt(
                identity_type=identity_type,
                conversation_identity=conversation_identity,
            )
            .where(ConversationGrade.id != grade.id)
            .limit(history_limit)
        )
    ).all()
    conversation_key = _resolve_monitoring_conversation_key(grade)

    return [
        MonitoringConversationHistoryItem(
            grade_id=row.id,
            grade_date=row.grade_date,
            conversation_key=conversation_key,
            resolution=row.resolution,
            escalation_type=row.escalation_type,
            frustration_score=row.frustration_score,
            accuracy_score=row.accuracy_score,
            highlights=evaluate_monitoring_highlights(row, rules),
        )
        for row in rows
    ]


def _resolve_monitoring_conversation_key(grade: ConversationGrade) -> str:
    conversation_identity = _strip_or_none(grade.conversation_identity)
    if conversation_identity is not None:
        return encode_conversation_key(conversation_identity)

    phone_number = _strip_or_none(grade.phone_number)
    if phone_number is None:
        raise MonitoringConversationNotFoundError("Grade not found.")
    return encode_conversation_key(phone_number)


def _resolve_intent_code(intent_code: str | None) -> str | None:
    normalized = _strip_or_none(intent_code)
    if normalized is None:
        return None
    canonical = normalized.lower()
    return canonical if canonical in INTENT_CODE_TO_LABEL else None


def _resolve_intent_label(intent_code: str | None) -> str | None:
    canonical = _resolve_intent_code(intent_code)
    if canonical is None:
        return None
    return INTENT_CODE_TO_LABEL[canonical]


def _resolve_intent_category(intent_code: str | None) -> str | None:
    canonical = _resolve_intent_code(intent_code)
    if canonical is None:
        return None
    return INTENT_CODE_TO_CATEGORY.get(canonical)


def _build_monitoring_grade_panel(grade: ConversationGrade) -> MonitoringGradePanel:
    return MonitoringGradePanel(
        ai_performance={
            "relevancy_score": grade.relevancy_score,
            "relevancy_reasoning": grade.relevancy_reasoning,
            "accuracy_score": grade.accuracy_score,
            "accuracy_reasoning": grade.accuracy_reasoning,
            "completeness_score": grade.completeness_score,
            "completeness_reasoning": grade.completeness_reasoning,
            "clarity_score": grade.clarity_score,
            "clarity_reasoning": grade.clarity_reasoning,
            "tone_score": grade.tone_score,
            "tone_reasoning": grade.tone_reasoning,
        },
        conversation_health={
            "resolution": grade.resolution,
            "resolution_reasoning": grade.resolution_reasoning,
            "repetition_score": grade.repetition_score,
            "repetition_reasoning": grade.repetition_reasoning,
            "loop_detected": grade.loop_detected,
            "loop_detected_reasoning": grade.loop_detected_reasoning,
        },
        user_signals={
            "satisfaction_score": grade.satisfaction_score,
            "satisfaction_reasoning": grade.satisfaction_reasoning,
            "frustration_score": grade.frustration_score,
            "frustration_reasoning": grade.frustration_reasoning,
            "user_relevancy": grade.user_relevancy,
            "user_relevancy_reasoning": grade.user_relevancy_reasoning,
        },
        escalation={
            "escalation_occurred": grade.escalation_occurred,
            "escalation_occurred_reasoning": grade.escalation_occurred_reasoning,
            "escalation_type": grade.escalation_type,
            "escalation_type_reasoning": grade.escalation_type_reasoning,
        },
        intent={
            "intent_code": grade.intent_code,
            "intent_label": grade.intent_label,
            "intent_category": _resolve_intent_category(grade.intent_code),
            "intent_reasoning": grade.intent_reasoning,
        },
    )


def _to_monitoring_transcript_role(direction: str) -> str:
    if direction == "inbound":
        return "user"
    if direction == "outbound":
        return "assistant"
    return "system"


def _build_monitoring_chat_match_filters() -> tuple[Any, ...]:
    from app.services.grading_extraction import (
        canonical_identity_type_expr,
        canonical_identity_value_expr,
        gst_grade_date_expr,
    )

    return (
        canonical_identity_type_expr() == ConversationGrade.identity_type,
        canonical_identity_value_expr() == ConversationGrade.conversation_identity,
        gst_grade_date_expr() == ConversationGrade.grade_date,
    )


def _nullif_blank(column: Any):
    return func.nullif(func.btrim(cast(column, String())), "")


def _strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
