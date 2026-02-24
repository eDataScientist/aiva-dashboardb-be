from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_database(database_url: str) -> None:
    """Create async engine + session factory.  Swaps driver to asyncpg."""
    global _engine, _session_factory

    if _engine is not None:
        return

    # Swap driver: postgresql+psycopg2:// or postgresql:// → postgresql+asyncpg://
    async_url = database_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://", 1
    )
    async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    _engine = create_async_engine(async_url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return session factory or raise if not configured."""
    if _session_factory is None:
        raise RuntimeError("Session factory is not configured. Call configure_database first.")
    return _session_factory


async def check_database_connection() -> None:
    """Verify the database is reachable."""
    if _engine is None:
        raise RuntimeError("Database is not configured. Call configure_database first.")
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def close_database() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
