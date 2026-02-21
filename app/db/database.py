from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_database(database_url: str) -> None:
    global _engine, _session_factory

    if _engine is not None:
        return

    _engine = create_engine(database_url, future=True, pool_pre_ping=True)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def check_database_connection() -> None:
    if _engine is None:
        raise RuntimeError("Database is not configured. Call configure_database first.")

    with _engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        raise RuntimeError("Session factory is not configured. Call configure_database first.")
    return _session_factory


def close_database() -> None:
    global _engine, _session_factory

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None

