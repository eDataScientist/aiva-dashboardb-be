import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.core.security import create_access_token
from app.models.account import Account
from app.models.chats import ChatMessage
from datetime import datetime, timezone, timedelta
from app.services.conversations import encode_conversation_key


def _auth_headers(account: Account) -> dict[str, str]:
    token = create_access_token(
        subject=str(account.id),
        email=account.email,
        role=account.role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def active_account(db_session):
    account = Account(
        email="conversations.routes@example.com",
        password_hash="hashed-password",
        full_name="Conversations Routes",
        role="analyst",
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_api_list_conversations_happy_path(
    client: AsyncClient, db_session, active_account: Account
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    msg = ChatMessage(
        customer_phone="+971501234567",
        customer_name="Ahmed",
        message="I need a quote",
        direction="inbound",
        channel="whatsapp",
        message_type="text",
        created_at=now
    )
    db_session.add(msg)
    await db_session.commit()
    
    response = await client.get(
        "/api/v1/conversations?limit=10&offset=0&channel=all",
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["contact_name"] == "Ahmed"
    assert data["items"][0]["latest_message"] == "I need a quote"
    assert data["items"][0]["channel"] == "whatsapp"


@pytest.mark.asyncio
async def test_api_get_conversation_messages_happy_path(
    client: AsyncClient, db_session, active_account: Account
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    msg = ChatMessage(
        session_id="web-sess-1",
        customer_name="Web User",
        message="Hello World",
        direction="inbound",
        channel="web_chat",
        message_type="text",
        created_at=now
    )
    db_session.add(msg)
    await db_session.commit()
    
    conv_key = encode_conversation_key("web-sess-1")
    response = await client.get(
        f"/api/v1/conversations/{conv_key}/messages",
        headers=_auth_headers(active_account),
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["contact_name"] == "Web User"
    assert data["conversation_key"] == conv_key
    assert len(data["messages"]) == 1
    assert data["messages"][0]["message"] == "Hello World"


@pytest.mark.asyncio
async def test_api_list_conversations_validation_error(
    client: AsyncClient, active_account: Account
):
    # Invalid limit parameter
    response = await client.get(
        "/api/v1/conversations?limit=-1",
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    
    # Invalid channel parameter
    response2 = await client.get(
        "/api/v1/conversations?channel=unknown_channel",
        headers=_auth_headers(active_account),
    )
    assert response2.status_code == 422


@pytest.mark.asyncio
async def test_api_get_conversation_messages_not_found(
    client: AsyncClient, active_account: Account
):
    # Non-existent conversation
    conv_key = encode_conversation_key("nobody@nowhere.com")
    response = await client.get(
        f"/api/v1/conversations/{conv_key}/messages",
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


@pytest.mark.asyncio
async def test_api_get_conversation_messages_invalid_key_format(
    client: AsyncClient, active_account: Account
):
    # Fails path parameter regex validation
    response = await client.get(
        "/api/v1/conversations/invalid!key/messages",
        headers=_auth_headers(active_account),
    )
    assert response.status_code == 422
    
    # Passes regex but invalid base64 payload
    response2 = await client.get(
        "/api/v1/conversations/conv_not_base_64/messages",
        headers=_auth_headers(active_account),
    )
    assert response2.status_code == 404
