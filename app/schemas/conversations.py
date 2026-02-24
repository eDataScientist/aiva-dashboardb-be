from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.analytics import AnalyticsFilterQuery, SchemaModel


class ConversationsListQuery(AnalyticsFilterQuery):
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Page size for conversations list endpoint.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset for conversations pagination.",
    )


class ConversationPathParams(SchemaModel):
    conversation_key: str = Field(
        min_length=1,
        max_length=512,
        pattern=r"^[A-Za-z0-9_-]+$",
        description=(
            "Opaque URL-safe conversation identifier derived from the canonical identity "
            "(COALESCE(customer_phone, customer_email_address, session_id))."
        ),
    )


class ConversationSummaryItem(SchemaModel):
    conversation_key: str = Field(
        description="Opaque URL-safe token used to fetch the full conversation message history.",
    )
    contact_name: str | None = Field(
        default=None,
        description="Best available non-empty customer name (MVP: latest non-empty observed value).",
    )
    latest_message: str | None = Field(
        default=None,
        description="Most recent message payload (text or media/file URL).",
    )
    latest_message_type: str | None = Field(
        default=None,
        description="Message type for latest_message (text/image/file/audio/video/location/sticker/etc.).",
    )
    latest_message_at: datetime = Field(
        description="Most recent message timestamp for sorting (conversation list sorted descending by this field).",
    )
    message_count: int | None = Field(
        default=None,
        ge=0,
        description="Total number of messages observed for the conversation in the selected filter range.",
    )
    channel: str | None = Field(
        default=None,
        description="Channel associated with the latest message (or documented channel selection rule).",
    )


class ConversationListResponse(SchemaModel):
    items: list[ConversationSummaryItem] = Field(
        default_factory=list,
        description="Paginated conversation summaries sorted by latest_message_at descending.",
    )
    total: int = Field(
        ge=0,
        description="Total number of conversations matching the current filters before pagination.",
    )
    limit: int = Field(ge=1, description="Echoed page size.")
    offset: int = Field(ge=0, description="Echoed page offset.")


class ConversationMessageItem(SchemaModel):
    id: int = Field(ge=0, description="Source message row identifier.")
    created_at: datetime = Field(description="Message timestamp (response sorted ascending by this field).")
    direction: str = Field(description="Canonical direction value (inbound/outbound).")
    message: str | None = Field(
        default=None,
        description="Raw message payload (text content or media/file URL).",
    )
    message_type: str | None = Field(
        default=None,
        description="Message type used by frontend renderers (text/image/file/audio/video/location/sticker/etc.).",
    )
    channel: str | None = Field(default=None)
    intent: str | None = Field(default=None)
    escalated: str | None = Field(
        default=None,
        description="Raw legacy escalated value retained for transparency/compatibility.",
    )


class ConversationMessagesResponse(SchemaModel):
    conversation_key: str = Field(
        description="Opaque conversation identifier used in the request path.",
    )
    contact_name: str | None = Field(
        default=None,
        description="Best available non-empty customer name for the selected conversation.",
    )
    messages: list[ConversationMessageItem] = Field(
        default_factory=list,
        description="All conversation messages sorted ascending by created_at.",
    )
