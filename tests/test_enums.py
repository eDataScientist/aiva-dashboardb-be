import pytest
from app.models.enums import (
    ChannelType,
    DirectionType,
    EscalationType,
    MessageType,
    normalize_channel,
    normalize_direction,
    normalize_escalation_type,
    normalize_legacy_bool,
    normalize_message_type,
)


def test_normalize_legacy_bool():
    assert normalize_legacy_bool("1") is True
    assert normalize_legacy_bool("true") is True
    assert normalize_legacy_bool("yes") is True
    assert normalize_legacy_bool("y") is True
    assert normalize_legacy_bool("t") is True
    assert normalize_legacy_bool(1) is True
    assert normalize_legacy_bool(True) is True

    assert normalize_legacy_bool("0") is False
    assert normalize_legacy_bool("false") is False
    assert normalize_legacy_bool("no") is False
    assert normalize_legacy_bool("n") is False
    assert normalize_legacy_bool("f") is False
    assert normalize_legacy_bool(0) is False
    assert normalize_legacy_bool(False) is False

    assert normalize_legacy_bool(None) is None
    assert normalize_legacy_bool("invalid") is None
    assert normalize_legacy_bool(5) is None


def test_normalize_direction():
    assert normalize_direction("inbound") == DirectionType.INBOUND
    assert normalize_direction(" incoming ") == DirectionType.INBOUND
    assert normalize_direction("IN") == DirectionType.INBOUND
    assert normalize_direction("customer") == DirectionType.INBOUND

    assert normalize_direction("outbound") == DirectionType.OUTBOUND
    assert normalize_direction("outgoing") == DirectionType.OUTBOUND
    assert normalize_direction("OUT") == DirectionType.OUTBOUND
    assert normalize_direction("agent") == DirectionType.OUTBOUND

    assert normalize_direction(None) is None
    assert normalize_direction("alien") is None


def test_normalize_channel():
    assert normalize_channel("wa") == ChannelType.WHATSAPP
    assert normalize_channel("WHATSAPP") == ChannelType.WHATSAPP
    
    assert normalize_channel("web") == ChannelType.WEB
    assert normalize_channel("webchat") == ChannelType.WEB
    assert normalize_channel("web_chat") == ChannelType.WEB
    assert normalize_channel("website") == ChannelType.WEB

    assert normalize_channel(None) is None
    assert normalize_channel("telegram") is None


def test_normalize_message_type():
    assert normalize_message_type("text") == MessageType.TEXT
    assert normalize_message_type("message") == MessageType.TEXT
    assert normalize_message_type("photo") == MessageType.IMAGE
    assert normalize_message_type("image") == MessageType.IMAGE
    assert normalize_message_type("document") == MessageType.FILE
    assert normalize_message_type("file") == MessageType.FILE
    assert normalize_message_type("voice") == MessageType.AUDIO
    assert normalize_message_type("audio") == MessageType.AUDIO
    assert normalize_message_type("video") == MessageType.VIDEO
    assert normalize_message_type("loc") == MessageType.LOCATION
    assert normalize_message_type("location") == MessageType.LOCATION
    assert normalize_message_type("sticker") == MessageType.STICKER

    assert normalize_message_type(None) is None
    assert normalize_message_type("unknown_type") is None


def test_normalize_escalation_type():
    assert normalize_escalation_type("natural") == EscalationType.NATURAL
    assert normalize_escalation_type(" NATURAL ") == EscalationType.NATURAL
    assert normalize_escalation_type("failure") == EscalationType.FAILURE
    assert normalize_escalation_type("none") == EscalationType.NONE

    assert normalize_escalation_type(None) is None
    assert normalize_escalation_type("fake") is None
