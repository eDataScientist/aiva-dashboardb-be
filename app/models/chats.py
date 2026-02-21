from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import quoted_name

from app.db.base import Base
from app.models.enums import (
    ChannelType,
    DirectionType,
    MessageType,
    normalize_channel,
    normalize_direction,
    normalize_legacy_bool,
    normalize_message_type,
)


class ChatMessage(Base):
    __tablename__ = quoted_name("Arabia Insurance Chats", True)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    message_type: Mapped[str | None] = mapped_column(String(32), nullable=True, default="text")
    intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Keep this as string-compatible in the initial contract because source data is mixed text/bool.
    escalated: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    @validates("direction")
    def _validate_direction(self, _key: str, value: str) -> str:
        normalized = normalize_direction(value)
        if normalized is None:
            raise ValueError(f"Unsupported direction value: {value!r}")
        return normalized.value

    @validates("channel")
    def _validate_channel(self, _key: str, value: str) -> str:
        normalized = normalize_channel(value)
        if normalized is None:
            return ChannelType.UNKNOWN.value
        return normalized.value

    @validates("message_type")
    def _validate_message_type(self, _key: str, value: str | None) -> str:
        normalized = normalize_message_type(value)
        if normalized is None:
            return MessageType.TEXT.value
        return normalized.value

    @property
    def escalated_bool(self) -> bool | None:
        return normalize_legacy_bool(self.escalated)

    @property
    def direction_enum(self) -> DirectionType | None:
        return normalize_direction(self.direction)

    @property
    def channel_enum(self) -> ChannelType | None:
        return normalize_channel(self.channel)

    @property
    def message_type_enum(self) -> MessageType | None:
        return normalize_message_type(self.message_type)

    @property
    def customer_identity_key(self) -> str | None:
        return self.customer_phone or self.customer_email_address or self.session_id
