from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-compatible dependency that yields an async DB session and closes it after the request."""
    async with get_session_factory()() as session:
        yield session
