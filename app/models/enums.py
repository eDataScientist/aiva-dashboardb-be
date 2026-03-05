from __future__ import annotations

from enum import Enum
from typing import Any


class DirectionType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    WEB = "web"
    UNKNOWN = "unknown"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    STICKER = "sticker"
    UNKNOWN = "unknown"


class EscalationType(str, Enum):
    NATURAL = "Natural"
    FAILURE = "Failure"
    NONE = "None"


class IdentityType(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    SESSION = "session"


class AccountRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    COMPANY_ADMIN = "company_admin"
    ANALYST = "analyst"


_TRUE_VALUES = {"1", "true", "yes", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "n", "f"}

_DIRECTION_ALIASES = {
    "inbound": DirectionType.INBOUND,
    "incoming": DirectionType.INBOUND,
    "in": DirectionType.INBOUND,
    "customer": DirectionType.INBOUND,
    "outbound": DirectionType.OUTBOUND,
    "outgoing": DirectionType.OUTBOUND,
    "out": DirectionType.OUTBOUND,
    "agent": DirectionType.OUTBOUND,
}

_CHANNEL_ALIASES = {
    "wa": ChannelType.WHATSAPP,
    "whatsapp": ChannelType.WHATSAPP,
    "web": ChannelType.WEB,
    "website": ChannelType.WEB,
    "webchat": ChannelType.WEB,
    "web_chat": ChannelType.WEB,
}

_MESSAGE_TYPE_ALIASES = {
    "text": MessageType.TEXT,
    "message": MessageType.TEXT,
    "image": MessageType.IMAGE,
    "photo": MessageType.IMAGE,
    "file": MessageType.FILE,
    "document": MessageType.FILE,
    "audio": MessageType.AUDIO,
    "voice": MessageType.AUDIO,
    "video": MessageType.VIDEO,
    "location": MessageType.LOCATION,
    "loc": MessageType.LOCATION,
    "sticker": MessageType.STICKER,
}

_ESCALATION_TYPE_ALIASES = {
    "natural": EscalationType.NATURAL,
    "failure": EscalationType.FAILURE,
    "none": EscalationType.NONE,
}

_IDENTITY_TYPE_ALIASES = {
    "phone": IdentityType.PHONE,
    "email": IdentityType.EMAIL,
    "session": IdentityType.SESSION,
}

_ACCOUNT_ROLE_ALIASES = {
    "super_admin": AccountRole.SUPER_ADMIN,
    "company_admin": AccountRole.COMPANY_ADMIN,
    "analyst": AccountRole.ANALYST,
}


def _as_token(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        token = raw_value.strip()
        return token.lower() if token else None
    if isinstance(raw_value, Enum):
        return str(raw_value.value).strip().lower()
    return str(raw_value).strip().lower() or None


def normalize_legacy_bool(raw_value: Any) -> bool | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, bool):
        return raw_value

    if isinstance(raw_value, (int, float)) and raw_value in (0, 1):
        return bool(raw_value)

    token = _as_token(raw_value)
    if token in _TRUE_VALUES:
        return True
    if token in _FALSE_VALUES:
        return False
    return None


def normalize_direction(raw_value: Any) -> DirectionType | None:
    token = _as_token(raw_value)
    if token is None:
        return None
    return _DIRECTION_ALIASES.get(token)


def normalize_channel(raw_value: Any) -> ChannelType | None:
    token = _as_token(raw_value)
    if token is None:
        return None
    return _CHANNEL_ALIASES.get(token)


def normalize_message_type(raw_value: Any) -> MessageType | None:
    token = _as_token(raw_value)
    if token is None:
        return None
    return _MESSAGE_TYPE_ALIASES.get(token)


def normalize_escalation_type(raw_value: Any) -> EscalationType | None:
    token = _as_token(raw_value)
    if token is None:
        return None
    return _ESCALATION_TYPE_ALIASES.get(token)


def normalize_identity_type(raw_value: Any) -> IdentityType | None:
    token = _as_token(raw_value)
    if token is None:
        return None
    return _IDENTITY_TYPE_ALIASES.get(token)


def normalize_account_role(raw_value: Any) -> AccountRole | None:
    token = _as_token(raw_value)
    if token is None:
        return None
    return _ACCOUNT_ROLE_ALIASES.get(token)
