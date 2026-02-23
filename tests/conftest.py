import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

# Disable Ryuk Reaper to avoid port 8080 binding issues on Windows
os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

# Set dummy DATABASE_URL so that app.main import and get_settings() doesn't fail
os.environ["DATABASE_URL"] = "postgresql://dummy:dummy@localhost:5432/dummy"

from app.db import database
from app.db.deps import get_db
from app.main import app

@pytest.fixture(scope="session")
def postgres_container():
    """Start an ephemeral PostgreSQL DB for the entire test session."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def engine_setup(postgres_container):
    """Run Alembic migrations on the ephemeral DB and configure the async engine."""
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
    
    # Configure the global application database using the async driver
    # configure_database swaps postgresql:// to postgresql+asyncpg://
    database.configure_database(db_url)
    
    yield db_url

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
            autoflush=False
        )
        session = session_factory()

        @pytest_asyncio.fixture(autouse=True)
        async def automatic_savepoint_rollback():
            # Rollback to the savepoint if a nested transaction was committed or rolled back
            if not conn.in_nested_transaction():
                await conn.begin_nested()
                
        yield session

        # Close session and rollback the top-level transaction
        await session.close()
        await conn.rollback()

@pytest.fixture()
def client(db_session):
    """
    Provides an AsyncClient connected to the FastAPI app, 
    with the db dependency overridden to use the function-scoped test session.
    """
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    # We yield the class instantiaton so they can use it as a context manager manually if they want to
    # but normally this fixture would just return the instance or yield it
    # Here, we'll return an initialized AsyncClient
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client
    
    app.dependency_overrides.clear()
