from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Integer, String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.chats import ChatMessage
from app.models.enums import (
    IdentityType,
    normalize_channel,
    normalize_direction,
    normalize_identity_type,
    normalize_legacy_bool,
    normalize_message_type,
)

REPORTING_TIMEZONE = "Asia/Dubai"


@dataclass(frozen=True, slots=True)
class CustomerDayCandidate:
    identity_type: IdentityType
    conversation_identity: str
    grade_date: date


@dataclass(frozen=True, slots=True)
class TranscriptMessage:
    chat_id: int
    created_at: datetime
    direction: str
    channel: str
    message_type: str
    message: str | None
    intent: str | None
    escalated: bool | None
    normalized_content: str
    transcript_line: str


@dataclass(frozen=True, slots=True)
class CustomerDayTranscript:
    candidate: CustomerDayCandidate
    messages: tuple[TranscriptMessage, ...] = field(default_factory=tuple)
    transcript_text: str = ""


def resolve_canonical_identity(
    customer_phone: str | None,
    customer_email_address: str | None,
    session_id: str | None,
) -> tuple[IdentityType | None, str | None]:
    for identity_type, raw_value in (
        (IdentityType.PHONE, customer_phone),
        (IdentityType.EMAIL, customer_email_address),
        (IdentityType.SESSION, session_id),
    ):
        normalized = _strip_or_none(raw_value)
        if normalized is not None:
            return identity_type, normalized
    return None, None


def canonical_identity_value_expr():
    return func.coalesce(
        _nullif_blank(ChatMessage.customer_phone),
        _nullif_blank(ChatMessage.customer_email_address),
        _nullif_blank(ChatMessage.session_id),
    )


def canonical_identity_type_expr():
    phone_expr = _nullif_blank(ChatMessage.customer_phone)
    email_expr = _nullif_blank(ChatMessage.customer_email_address)
    session_expr = _nullif_blank(ChatMessage.session_id)
    return case(
        (phone_expr.is_not(None), IdentityType.PHONE.value),
        (email_expr.is_not(None), IdentityType.EMAIL.value),
        (session_expr.is_not(None), IdentityType.SESSION.value),
        else_=None,
    )


def gst_timestamp_expr(column: Any = ChatMessage.created_at):
    return func.timezone(REPORTING_TIMEZONE, column)


def gst_grade_date_expr(column: Any = ChatMessage.created_at):
    return cast(gst_timestamp_expr(column), Date)


def gst_grade_hour_expr(column: Any = ChatMessage.created_at):
    return cast(func.extract("HOUR", gst_timestamp_expr(column)), Integer)


def build_customer_day_candidates_stmt(
    start_date: date | None = None,
    end_date: date | None = None,
) -> Select[Any]:
    identity_type_expr = canonical_identity_type_expr()
    identity_value_expr = canonical_identity_value_expr()
    grade_date_expr = gst_grade_date_expr()

    stmt = (
        select(
            identity_type_expr.label("identity_type"),
            identity_value_expr.label("conversation_identity"),
            grade_date_expr.label("grade_date"),
        )
        .where(identity_value_expr.is_not(None))
        .distinct()
        .order_by(grade_date_expr.asc(), identity_type_expr.asc(), identity_value_expr.asc())
    )

    if start_date is not None:
        stmt = stmt.where(grade_date_expr >= start_date)
    if end_date is not None:
        stmt = stmt.where(grade_date_expr <= end_date)
    return stmt


def build_customer_day_messages_stmt(candidate: CustomerDayCandidate) -> Select[Any]:
    grade_date_expr = gst_grade_date_expr()
    identity_type_expr = canonical_identity_type_expr()
    identity_value_expr = canonical_identity_value_expr()

    return (
        select(
            ChatMessage.id,
            ChatMessage.created_at,
            ChatMessage.direction,
            ChatMessage.channel,
            ChatMessage.message_type,
            ChatMessage.message,
            ChatMessage.intent,
            ChatMessage.escalated,
        )
        .where(identity_type_expr == candidate.identity_type.value)
        .where(identity_value_expr == candidate.conversation_identity)
        .where(grade_date_expr == candidate.grade_date)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )


async def list_customer_day_candidates(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[CustomerDayCandidate]:
    rows = (
        await session.execute(
            build_customer_day_candidates_stmt(start_date=start_date, end_date=end_date)
        )
    ).mappings()

    candidates: list[CustomerDayCandidate] = []
    for row in rows:
        candidate = _coerce_customer_day_candidate(
            identity_type=row.get("identity_type"),
            conversation_identity=row.get("conversation_identity"),
            grade_date=row.get("grade_date"),
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


async def assemble_customer_day_transcript(
    session: AsyncSession,
    candidate: CustomerDayCandidate,
) -> CustomerDayTranscript:
    rows = (await session.execute(build_customer_day_messages_stmt(candidate))).mappings()
    messages = tuple(_coerce_transcript_message(row) for row in rows)
    return CustomerDayTranscript(
        candidate=candidate,
        messages=messages,
        transcript_text=_render_transcript_text(messages),
    )


def _nullif_blank(column):
    return func.nullif(func.btrim(cast(column, String())), "")


def _coerce_transcript_message(row: Any) -> TranscriptMessage:
    chat_id = _coerce_chat_id(row.get("id"))
    created_at = _coerce_datetime(row.get("created_at"))
    direction = _normalize_direction_value(row.get("direction"))
    channel = _normalize_channel_value(row.get("channel"))
    message_type = _normalize_message_type_value(row.get("message_type"))
    message = _normalize_transcript_text(row.get("message"))
    intent = _normalize_transcript_text(row.get("intent"))
    escalated = normalize_legacy_bool(row.get("escalated"))
    normalized_content = _normalize_transcript_content(message_type, message)
    transcript_line = _format_transcript_line(
        created_at=created_at,
        direction=direction,
        channel=channel,
        message_type=message_type,
        intent=intent,
        escalated=escalated,
        normalized_content=normalized_content,
    )

    return TranscriptMessage(
        chat_id=chat_id,
        created_at=created_at,
        direction=direction,
        channel=channel,
        message_type=message_type,
        message=message,
        intent=intent,
        escalated=escalated,
        normalized_content=normalized_content,
        transcript_line=transcript_line,
    )


def _coerce_customer_day_candidate(
    identity_type: Any,
    conversation_identity: Any,
    grade_date: Any,
) -> CustomerDayCandidate | None:
    normalized_identity_type = normalize_identity_type(identity_type)
    normalized_identity = _strip_or_none(conversation_identity)
    normalized_grade_date = _coerce_date(grade_date)

    if (
        normalized_identity_type is None
        or normalized_identity is None
        or normalized_grade_date is None
    ):
        return None

    return CustomerDayCandidate(
        identity_type=normalized_identity_type,
        conversation_identity=normalized_identity,
        grade_date=normalized_grade_date,
    )


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _coerce_chat_id(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Transcript chat_id cannot be boolean.")
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Transcript chat_id is invalid.") from exc


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raise ValueError("Transcript created_at must be a datetime value.")


def _normalize_direction_value(raw_value: Any) -> str:
    value = _strip_or_none(raw_value)
    if value is None:
        return "unknown"
    normalized = normalize_direction(value)
    return normalized.value if normalized is not None else value.lower()


def _normalize_channel_value(raw_value: Any) -> str:
    value = _strip_or_none(raw_value)
    if value is None:
        return "unknown"
    normalized = normalize_channel(value)
    return normalized.value if normalized is not None else value.lower()


def _normalize_message_type_value(raw_value: Any) -> str:
    value = _strip_or_none(raw_value)
    if value is None:
        return "text"
    normalized = normalize_message_type(value)
    return normalized.value if normalized is not None else value.lower()


def _normalize_transcript_content(message_type: str, message: str | None) -> str:
    if message_type == "text":
        return message or "[empty text message]"
    if message is None:
        return f"[{message_type} attachment]"
    return f"[{message_type} attachment] {message}"


def _format_transcript_line(
    *,
    created_at: datetime,
    direction: str,
    channel: str,
    message_type: str,
    intent: str | None,
    escalated: bool | None,
    normalized_content: str,
) -> str:
    intent_token = intent or "<none>"
    escalated_token = _format_escalated_token(escalated)
    return (
        f"{created_at.isoformat()} | "
        f"direction={direction} | "
        f"channel={channel} | "
        f"message_type={message_type} | "
        f"escalated={escalated_token} | "
        f"intent={intent_token} | "
        f"content={normalized_content}"
    )


def _render_transcript_text(messages: tuple[TranscriptMessage, ...]) -> str:
    return "\n".join(message.transcript_line for message in messages)


def _format_escalated_token(value: bool | None) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def _normalize_transcript_text(value: Any) -> str | None:
    normalized = _strip_or_none(value)
    if normalized is None:
        return None
    return " ".join(normalized.split())


def _strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
