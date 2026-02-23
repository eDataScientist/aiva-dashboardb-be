from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db
from app.schemas.conversations import (
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationsListQuery,
)
from app.services.conversations import (
    ConversationNotFoundError,
    get_conversation_messages as get_conversation_messages_response,
    list_conversations,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List conversations by recency",
)
async def list_conversations_endpoint(
    filters: Annotated[ConversationsListQuery, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationListResponse:
    return await list_conversations(db, filters)


@router.get(
    "/{conversation_key}/messages",
    response_model=ConversationMessagesResponse,
    summary="Get full message history for one conversation",
    responses={
        404: {
            "description": "Conversation key was invalid or no conversation matched it.",
            "content": {
                "application/json": {
                    "example": {"detail": "Conversation not found"},
                }
            },
        }
    },
)
async def get_conversation_messages_endpoint(
    conversation_key: Annotated[
        str,
        Path(
            ...,
            min_length=1,
            max_length=512,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Opaque URL-safe conversation identifier returned by the conversations list endpoint.",
        ),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationMessagesResponse:
    try:
        return await get_conversation_messages_response(db, conversation_key)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
