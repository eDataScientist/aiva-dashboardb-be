import pytest
from datetime import datetime, timezone, timedelta
from app.models.chats import ChatMessage
from app.schemas.conversations import ConversationsListQuery
from app.services.conversations import (
    list_conversations,
    get_conversation_messages,
    encode_conversation_key,
)
from app.schemas.analytics import AnalyticsChannelFilter

@pytest.mark.asyncio
async def test_list_conversations_happy_path(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Conversation 1: User Alpha
    msg1 = ChatMessage(
        customer_phone="+12345",
        customer_name="Alpha",
        message="Hello",
        direction="inbound",
        channel="whatsapp",
        message_type="text",
        created_at=now - timedelta(days=2)
    )
    msg2 = ChatMessage(
        customer_phone="+12345",
        customer_name="Alpha User",
        message="How are you?",
        direction="inbound",
        channel="whatsapp",
        message_type="text",
        created_at=now - timedelta(days=1)
    )
    
    # Conversation 2: User Beta
    msg3 = ChatMessage(
        session_id="sess-abc",
        customer_name=None,
        message="I need help",
        direction="inbound",
        channel="web_chat",
        message_type="text",
        created_at=now - timedelta(hours=5)
    )
    msg4 = ChatMessage(
        session_id="sess-abc",
        customer_name="Beta",
        message="Are you there?",
        direction="inbound",
        channel="web_chat",
        message_type="text",
        created_at=now - timedelta(hours=4)
    )
    
    db_session.add_all([msg1, msg2, msg3, msg4])
    await db_session.commit()
    
    # query
    query = ConversationsListQuery(limit=10, offset=0, channel=AnalyticsChannelFilter.ALL)
    response = await list_conversations(db_session, query)
    
    assert response.total == 2
    assert len(response.items) == 2
    
    # Beta's message is the most recent (now - 4h vs now - 1d)
    item0 = response.items[0]
    item1 = response.items[1]
    
    assert item0.contact_name == "Beta"
    assert item0.latest_message == "Are you there?"
    assert item0.message_count == 2
    assert item0.conversation_key == encode_conversation_key("sess-abc")
    assert item0.channel == "web"
    
    assert item1.contact_name == "Alpha User"
    assert item1.latest_message == "How are you?"
    assert item1.message_count == 2
    assert item1.conversation_key == encode_conversation_key("+12345")
    assert item1.channel == "whatsapp"


@pytest.mark.asyncio
async def test_get_conversation_messages_happy_path(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    msg1 = ChatMessage(
        customer_email_address="charlie@example.com",
        customer_name="Charlie",
        message="First msg",
        direction="inbound",
        channel="email",
        created_at=now - timedelta(hours=2)
    )
    msg2 = ChatMessage(
        customer_email_address="charlie@example.com",
        customer_name="Charlie",
        message="Reply msg",
        direction="outbound",
        channel="email",
        created_at=now - timedelta(hours=1)
    )
    
    db_session.add_all([msg1, msg2])
    await db_session.commit()
    
    conv_key = encode_conversation_key("charlie@example.com")
    
    response = await get_conversation_messages(db_session, conv_key)
    
    assert response.conversation_key == conv_key
    assert response.contact_name == "Charlie"
    assert len(response.messages) == 2
    
    # Chronological check 
    assert response.messages[0].message == "First msg"
    assert response.messages[0].direction == "inbound"
    
    assert response.messages[1].message == "Reply msg"
    assert response.messages[1].direction == "outbound"


@pytest.mark.asyncio
async def test_list_conversations_pagination_and_filter(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # 3 web_chat conversations, 1 whatsapp conversation
    messages = []
    for i in range(3):
        messages.append(ChatMessage(
            session_id=f"sess-{i}",
            message=f"Web Message {i}",
            direction="inbound",
            channel="web_chat",
            created_at=now - timedelta(hours=i)  # i=0 is newest
        ))
    messages.append(ChatMessage(
        customer_phone="+9999",
        message="WhatsApp Message",
        direction="inbound",
        channel="whatsapp",
        created_at=now - timedelta(hours=5)
    ))
    
    db_session.add_all(messages)
    await db_session.commit()
    
    # Test filtering by channel
    query = ConversationsListQuery(limit=10, offset=0, channel=AnalyticsChannelFilter.WEB)
    response = await list_conversations(db_session, query)
    
    assert response.total == 3
    assert len(response.items) == 3
    assert all(item.channel == "web" for item in response.items)
    
    # Test pagination (limit 2, offset 1) without channel filter
    query_page = ConversationsListQuery(limit=2, offset=1, channel=AnalyticsChannelFilter.ALL)
    response_page = await list_conversations(db_session, query_page)
    
    assert response_page.total == 4
    assert len(response_page.items) == 2
    # Newest to oldest: sess-0, sess-1, sess-2, +9999
    # Offset 1 should return sess-1 and sess-2
    assert response_page.items[0].latest_message == "Web Message 1"
    assert response_page.items[1].latest_message == "Web Message 2"


@pytest.mark.asyncio
async def test_get_conversation_messages_not_found(db_session):
    from app.services.conversations import ConversationNotFoundError
    
    conv_key = encode_conversation_key("nobody@example.com")
    with pytest.raises(ConversationNotFoundError, match="Conversation not found"):
        await get_conversation_messages(db_session, conv_key)


@pytest.mark.asyncio
async def test_get_conversation_messages_invalid_key(db_session):
    from app.services.conversations import ConversationNotFoundError
    
    with pytest.raises(ConversationNotFoundError, match="Conversation not found"):
        await get_conversation_messages(db_session, "invalid-key-no-prefix")
        
    with pytest.raises(ConversationNotFoundError, match="Conversation not found"):
        await get_conversation_messages(db_session, "conv_invalid-base64-!")
