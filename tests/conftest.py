import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

# Disable Ryuk Reaper to avoid port 8080 binding issues on Windows
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Set dummy DATABASE_URL so that app.main import and get_settings() doesn't fail
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")
os.environ.setdefault(
    "AUTH_JWT_SECRET",
    "test-only-auth-secret-minimum-length-32",
)
os.environ.setdefault("AUTH_JWT_ALGORITHM", "HS256")
os.environ.setdefault("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from app.db import database
from app.db.deps import get_db
from app.main import app
from app.models.chats import ChatMessage

@pytest.fixture(scope="session")
def postgres_container():
    """Start an ephemeral PostgreSQL DB for the entire test session."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def migrated_db_url(postgres_container):
    """Run Alembic migrations once on the ephemeral DB and return the DB URL."""
    # Get the synchronous URL for Alembic
    db_url = postgres_container.get_connection_url()
    
    # Set the environment variable for alembic/env.py
    os.environ["DATABASE_URL"] = db_url

    # Run migrations
    import alembic.config
    import alembic.command
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    
    yield db_url


@pytest_asyncio.fixture()
async def engine_setup(migrated_db_url):
    """Configure the async engine for the current test and ensure chat table exists."""
    database.configure_database(migrated_db_url)
    
    # Force NullPool for tests
    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import create_async_engine
    async_url = migrated_db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1).replace("postgresql://", "postgresql+asyncpg://", 1)
    database._engine = create_async_engine(async_url, poolclass=NullPool)
    database._session_factory.configure(bind=database._engine)

    if database._engine is None:
        raise RuntimeError("Engine was not configured in test setup")

    async with database._engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: ChatMessage.__table__.create(
                bind=sync_conn, checkfirst=True
            )
        )

    try:
        yield migrated_db_url
    finally:
        await database.close_database()

@pytest_asyncio.fixture()
async def db_session(engine_setup):
    """
    Yields an AsyncSession scoped to a single test function.
    Rolls back the test's transaction after it completes.
    """
    if database._engine is None:
        raise RuntimeError("Engine not initialized in tests")

    # Connect to the engine and begin a transaction
    async with database._engine.connect() as conn:
        await conn.begin()
        # Begin a nested transaction (savepoint).
        # Ensures tests can do their own commits and rollbacks without affecting the top-level transaction.
        await conn.begin_nested()

        session_factory = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            class_=AsyncSession,
            autoflush=False,
        )
        session = session_factory()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_nested_transaction(_, __):
            # Recreate the savepoint after a test-level commit/rollback.
            if (
                conn.sync_connection is not None
                and conn.sync_connection.in_transaction()
                and not conn.sync_connection.in_nested_transaction()
            ):
                conn.sync_connection.begin_nested()

        try:
            yield session
        finally:
            event.remove(
                session.sync_session,
                "after_transaction_end",
                restart_nested_transaction,
            )
            await session.close()
            if conn.in_transaction():
                await conn.rollback()

@pytest_asyncio.fixture()
async def client(db_session):
    """
    Provides an AsyncClient connected to the FastAPI app, 
    with the db dependency overridden to use the function-scoped test session.
    """
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()
