from __future__ import annotations

import base64
import binascii
from typing import Any

from sqlalchemy import Date, String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chats import ChatMessage
from app.models.enums import normalize_channel, normalize_direction, normalize_message_type
from app.schemas.analytics import AnalyticsChannelFilter
from app.schemas.conversations import (
    ConversationListResponse,
    ConversationMessageItem,
    ConversationMessagesResponse,
    ConversationSummaryItem,
    ConversationsListQuery,
)

REPORTING_TIMEZONE = "Asia/Dubai"
_CONVERSATION_KEY_PREFIX = "conv_"


class ConversationNotFoundError(ValueError):
    """Raised when a conversation key is invalid or does not match any messages."""


def encode_conversation_key(identity: str) -> str:
    raw = identity.encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{_CONVERSATION_KEY_PREFIX}{token}"


def decode_conversation_key(conversation_key: str) -> str:
    if not conversation_key.startswith(_CONVERSATION_KEY_PREFIX):
        raise ValueError("Invalid conversation key prefix.")

    payload = conversation_key.removeprefix(_CONVERSATION_KEY_PREFIX)
    if not payload:
        raise ValueError("Empty conversation key payload.")

    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        value = decoded.decode("utf-8").strip()
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("Invalid conversation key encoding.") from exc

    if not value:
        raise ValueError("Conversation key resolved to an empty identity.")
    return value


async def list_conversations(session: AsyncSession, query: ConversationsListQuery) -> ConversationListResponse:
    identity_expr = _canonical_identity_expr()
    contact_name_expr = _nullif_blank(ChatMessage.customer_name)

    filters = [identity_expr.is_not(None), *_build_filters(query)]

    filtered = (
        select(
            ChatMessage.id.label("id"),
            identity_expr.label("conversation_identity"),
            contact_name_expr.label("contact_name"),
            ChatMessage.message.label("message"),
            ChatMessage.message_type.label("message_type"),
            ChatMessage.created_at.label("created_at"),
            ChatMessage.channel.label("channel"),
        )
        .where(*filters)
        .subquery("filtered_conversations")
    )

    latest_ranked = (
        select(
            filtered.c.id,
            filtered.c.conversation_identity,
            filtered.c.message.label("latest_message"),
            filtered.c.message_type.label("latest_message_type"),
            filtered.c.created_at.label("latest_message_at"),
            filtered.c.channel.label("channel"),
            func.count().over(partition_by=filtered.c.conversation_identity).label("message_count"),
            func.row_number()
            .over(
                partition_by=filtered.c.conversation_identity,
                order_by=(filtered.c.created_at.desc(), filtered.c.id.desc()),
            )
            .label("latest_row_number"),
        )
        .subquery("latest_ranked")
    )

    latest_only = (
        select(
            latest_ranked.c.id,
            latest_ranked.c.conversation_identity,
            latest_ranked.c.latest_message,
            latest_ranked.c.latest_message_type,
            latest_ranked.c.latest_message_at,
            latest_ranked.c.channel,
            latest_ranked.c.message_count,
        )
        .where(latest_ranked.c.latest_row_number == 1)
        .subquery("latest_only")
    )

    name_ranked = (
        select(
            filtered.c.conversation_identity,
            filtered.c.contact_name,
            func.row_number()
            .over(
                partition_by=filtered.c.conversation_identity,
                order_by=(
                    case((filtered.c.contact_name.is_(None), 1), else_=0),
                    filtered.c.created_at.desc(),
                    filtered.c.id.desc(),
                ),
            )
            .label("name_row_number"),
        )
        .subquery("name_ranked")
    )

    best_names = (
        select(
            name_ranked.c.conversation_identity,
            name_ranked.c.contact_name,
        )
        .where(name_ranked.c.name_row_number == 1)
        .subquery("best_names")
    )

    total = (await session.scalar(select(func.count()).select_from(latest_only))) or 0

    page_stmt = (
        select(
            latest_only.c.conversation_identity,
            best_names.c.contact_name,
            latest_only.c.latest_message,
            latest_only.c.latest_message_type,
            latest_only.c.latest_message_at,
            latest_only.c.message_count,
            latest_only.c.channel,
        )
        .select_from(
            latest_only.outerjoin(
                best_names,
                best_names.c.conversation_identity == latest_only.c.conversation_identity,
            )
        )
        .order_by(latest_only.c.latest_message_at.desc(), latest_only.c.id.desc())
        .limit(query.limit)
        .offset(query.offset)
    )

    rows = (await session.execute(page_stmt)).all()
    items = [
        ConversationSummaryItem(
            conversation_key=encode_conversation_key(row.conversation_identity),
            contact_name=_strip_or_none(row.contact_name),
            latest_message=row.latest_message,
            latest_message_type=_normalize_message_type_value(row.latest_message_type),
            latest_message_at=row.latest_message_at,
            message_count=int(row.message_count) if row.message_count is not None else None,
            channel=_normalize_channel_value(row.channel),
        )
        for row in rows
    ]

    return ConversationListResponse(items=items, total=int(total), limit=query.limit, offset=query.offset)


async def get_conversation_messages(
    session: AsyncSession,
    conversation_key: str,
) -> ConversationMessagesResponse:
    try:
        conversation_identity = decode_conversation_key(conversation_key)
    except ValueError as exc:
        raise ConversationNotFoundError("Conversation not found.") from exc

    identity_expr = _canonical_identity_expr()
    stmt = (
        select(
            ChatMessage.id,
            ChatMessage.created_at,
            ChatMessage.direction,
            ChatMessage.message,
            ChatMessage.message_type,
            ChatMessage.channel,
            ChatMessage.intent,
            ChatMessage.escalated,
            ChatMessage.customer_name,
        )
        .where(identity_expr == conversation_identity)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )

    rows = (await session.execute(stmt)).all()
    if not rows:
        raise ConversationNotFoundError("Conversation not found.")

    contact_name: str | None = None
    messages: list[ConversationMessageItem] = []
    for row in rows:
        candidate_name = _strip_or_none(row.customer_name)
        if candidate_name is not None:
            contact_name = candidate_name

        messages.append(
            ConversationMessageItem(
                id=row.id,
                created_at=row.created_at,
                direction=_normalize_direction_value(row.direction),
                message=row.message,
                message_type=_normalize_message_type_value(row.message_type),
                channel=_normalize_channel_value(row.channel),
                intent=_strip_or_none(row.intent),
                escalated=None if row.escalated is None else str(row.escalated),
            )
        )

    return ConversationMessagesResponse(
        conversation_key=conversation_key,
        contact_name=contact_name,
        messages=messages,
    )


def _build_filters(query: ConversationsListQuery) -> list[Any]:
    filters: list[Any] = []

    if query.channel != AnalyticsChannelFilter.ALL:
        filters.append(func.lower(ChatMessage.channel) == query.channel.value)

    gst_date_expr = _gst_date_expr()
    if query.start_date is not None:
        filters.append(gst_date_expr >= query.start_date)
    if query.end_date is not None:
        filters.append(gst_date_expr <= query.end_date)

    return filters


def _gst_date_expr():
    # Keep date bucketing semantics aligned with current analytics service implementation.
    return cast(func.timezone(REPORTING_TIMEZONE, ChatMessage.created_at), Date)


def _canonical_identity_expr():
    return func.coalesce(
        ChatMessage.customer_phone,
        ChatMessage.customer_email_address,
        ChatMessage.session_id,
    )


def _nullif_blank(column):
    return func.nullif(func.btrim(cast(column, String())), "")


def _strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    return stripped or None


def _normalize_channel_value(raw_value: Any) -> str | None:
    value = _strip_or_none(raw_value)
    if value is None:
        return None
    normalized = normalize_channel(value)
    return normalized.value if normalized is not None else value.lower()


def _normalize_message_type_value(raw_value: Any) -> str | None:
    value = _strip_or_none(raw_value)
    if value is None:
        return None
    normalized = normalize_message_type(value)
    return normalized.value if normalized is not None else value.lower()


def _normalize_direction_value(raw_value: Any) -> str:
    value = _strip_or_none(raw_value)
    if value is None:
        return "unknown"
    normalized = normalize_direction(value)
    return normalized.value if normalized is not None else value.lower()
