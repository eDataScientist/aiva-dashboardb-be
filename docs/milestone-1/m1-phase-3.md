# Milestone 1 - Phase 3 Plan: Async Database Migration

## Goals
- Port the entire database layer from synchronous SQLAlchemy (`Session`) to asynchronous (`AsyncSession`).
- Use `asyncpg` as the async PostgreSQL driver via `create_async_engine`.
- Ensure all service functions and route handlers use `await` for database operations.
- Keep all existing query logic unchanged — only the session wiring and async calls change.
- The app must be fully functional after migration (no hybrid sync+async state).

## Planning Analysis

### 1) Current Architecture

```text
main.py lifespan
  └─ configure_database(url)       ← create_engine (sync)
  └─ check_database_connection()   ← engine.connect() (sync)
  └─ close_database()              ← engine.dispose() (sync)

deps.py
  └─ get_db()                      ← yields Session (sync generator)

services/*.py
  └─ session.execute(query)        ← sync Session.execute()
  └─ session.scalar(query)         ← sync Session.scalar()

routes/*.py
  └─ async def endpoint(db: Session = Depends(get_db))
     └─ service_fn(session=db, ...)  ← sync call inside async handler
```

### 2) Target Architecture

```text
main.py lifespan
  └─ configure_database(url)           ← create_async_engine
  └─ await connect_database()          ← async with engine.connect()
  └─ await close_database()            ← await engine.dispose()

deps.py
  └─ async get_db()                    ← yields AsyncSession (async generator)

services/*.py
  └─ await session.execute(query)      ← AsyncSession.execute()
  └─ await session.scalar(query)       ← AsyncSession.scalar()

routes/*.py
  └─ async def endpoint(db: AsyncSession = Depends(get_db))
     └─ await service_fn(session=db, ...)  ← async call
```

### 3) Dependencies

**New package:**
| Package | Version | Purpose |
|---|---|---|
| `asyncpg` | `>=0.29.0,<1.0.0` | Async PostgreSQL driver for `create_async_engine("postgresql+asyncpg://...")` |

**Existing packages (no changes):**
- `sqlalchemy>=2.0.0` — already supports `ext.asyncio`
- `alembic` — stays sync (Alembic does not need async for migration execution)
- `psycopg2-binary` — kept for Alembic sync migrations

**URL scheme change:**
- Current: `postgresql://` or `postgresql+psycopg2://`
- Target: `postgresql+asyncpg://` for `create_async_engine`
- Alembic still uses the sync URL — `env.py` does not need changes

### 4) Configuration Changes

#### DATABASE_URL
The `Settings.database_url` validator in `app/core/config.py` currently accepts `postgresql://` and `postgres://` (aliasing to `postgresql://`).

For async, the engine needs the `postgresql+asyncpg://` scheme. Two options:
- **Option A**: Store `postgresql://` in env, swap scheme in `configure_database()` — cleaner DX, Alembic keeps working
- **Option B**: Store `postgresql+asyncpg://` in env, swap back for Alembic

**Decision: Option A** — `configure_database()` replaces `postgresql://` → `postgresql+asyncpg://` at engine-creation time. The raw URL in `.env` stays unchanged. Alembic's `env.py` continues to read `DATABASE_URL` directly.

### 5) File-by-File Change Specification

---

## Gate 3.0 — Async Foundation

| Task ID | Title | Type | Dependencies | Output |
|---|---|---|---|---|
| P1.3.1 | Add `asyncpg` dependency | Infra | `P1.2.10` | Updated `requirements.txt` |
| P1.3.2 | Rewrite `database.py` | DB | `P1.3.1` | Async engine + session factory |
| P1.3.3 | Rewrite `deps.py` | DB | `P1.3.2` | Async `get_db` dependency |
| P1.3.4 | Update `db/__init__.py` | DB | `P1.3.2` | Updated exports |
| P1.3.5 | Convert `analytics.py` service | API | `P1.3.3` | All analytics functions async |
| P1.3.6 | Convert `conversations.py` service | API | `P1.3.3` | All conversation functions async |
| P1.3.7 | Update analytics routes | API | `P1.3.5` | Routes use `AsyncSession` + `await` |
| P1.3.8 | Update conversations routes | API | `P1.3.6` | Routes use `AsyncSession` + `await` |
| P1.3.9 | Update `main.py` lifespan | Infra | `P1.3.2` | Async connect/disconnect |
| P1.3.10 | Smoke-test | QA | `P1.3.7-9` | App starts, `/health` returns 200 |

---

### P1.3.1 — Add `asyncpg` to `requirements.txt`

**File:** `requirements.txt`

```diff
 psycopg2-binary>=2.9.0,<3.0.0
+asyncpg>=0.29.0,<1.0.0
```

**Acceptance:**
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python -c "import asyncpg"` succeeds

---

### P1.3.2 — Rewrite `app/db/database.py`

**Current state** (sync):
```python
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

def configure_database(url: str) -> None: ...
def get_session_factory() -> sessionmaker[Session]: ...
def check_database_connection() -> None: ...
def close_database() -> None: ...
```

**Target state** (async):
```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

def configure_database(database_url: str) -> None:
    """Create engine + session factory. Swaps driver to asyncpg."""
    global _engine, _session_factory
    if _engine is not None:
        return
    # Swap driver: postgresql:// → postgresql+asyncpg://
    async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
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
        raise RuntimeError("Database not configured. Call configure_database() first.")
    return _session_factory

async def check_database_connection() -> None:
    """Verify the database is reachable."""
    if _engine is None:
        raise RuntimeError("Database not configured.")
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

async def close_database() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
```

**Key decisions:**
- `expire_on_commit=False` — prevents lazy-load attempts after commit in async context (lazy loading is not natively supported by `AsyncSession`)
- URL swap is string-based, handling `postgresql://` → `postgresql+asyncpg://`
- `psycopg2-binary` URL variants like `postgresql+psycopg2://` will also be handled

**Acceptance:**
- [ ] `configure_database(url)` creates an `AsyncEngine`
- [ ] `check_database_connection()` is `async` and executes `SELECT 1`
- [ ] `close_database()` is `async` and disposes engine

---

### P1.3.3 — Rewrite `app/db/deps.py`

**Current:**
```python
def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
```

**Target:**
```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with get_session_factory()() as session:
        yield session
```

The `async with` context manager on `AsyncSession` automatically closes the session when done.

**Acceptance:**
- [ ] `get_db` is an `async` generator
- [ ] Yields `AsyncSession`
- [ ] Session is closed automatically via context manager

---

### P1.3.4 — Update `app/db/__init__.py`

Update re-exports to reflect the new async functions:
- `configure_database`
- `check_database_connection`
- `close_database`
- `get_session_factory`
- `get_db`

Types to export: `AsyncSession` (re-exported for convenience in route type annotations).

**Acceptance:**
- [ ] `from app.db import get_db, AsyncSession` works

---

### P1.3.5 — Convert `app/services/analytics.py` to async

**Mechanical changes for all 8 functions:**

| Function | Current | Target |
|---|---|---|
| `get_analytics_summary` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |
| `get_message_volume_trend` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |
| `get_top_intents` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |
| `get_peak_hours` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |
| `compute_quality_trend` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |
| `compute_lead_conversion_trend` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |

**For each function:**
1. Change `def` → `async def`
2. Change type annotation `session: Session` → `session: AsyncSession`
3. Change every `session.execute(...)` → `await session.execute(...)`
4. Change every `session.scalar(...)` → `await session.scalar(...)`

**Unchanged:**
- All `select()`, `text()`, `func.*` query constructions stay identical
- All helper functions without DB access (`_get_default_date_range`, `_get_channel_filter`, `_convert_to_gst_date`, `_channel_sql_clause`, `_default_date_range`) stay sync
- All imports of `Session` → change to `AsyncSession`

**Acceptance:**
- [ ] All 8 service functions are `async def`
- [ ] All `session.execute()` calls are `await`ed
- [ ] Query objects are unchanged
- [ ] `from sqlalchemy.ext.asyncio import AsyncSession` replaces `from sqlalchemy.orm import Session`

---

### P1.3.6 — Convert `app/services/conversations.py` to async

Same mechanical pattern for all DB-accessing functions:

| Function | Current | Target |
|---|---|---|
| `list_conversations` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |
| `get_conversation_messages` | `def ...(session: Session, ...)` | `async def ...(session: AsyncSession, ...)` |

**Unchanged:**
- `encode_conversation_key`, `decode_conversation_key`, `_strip_or_none`, normalizers — all stay sync (no DB calls)
- All SQLAlchemy Core `select()` queries stay identical

**Acceptance:**
- [ ] `list_conversations` and `get_conversation_messages` are `async def`
- [ ] All `session.execute()` and `session.scalar()` calls are `await`ed
- [ ] `Session` import replaced with `AsyncSession`

---

### P1.3.7 — Update `app/api/routes/analytics.py`

**Changes per route handler (6 endpoints):**
1. Change `db: Annotated[Session, Depends(get_db)]` → `db: Annotated[AsyncSession, Depends(get_db)]`
2. Add `await` to every service function call:
   ```python
   # Before
   return _summary_service(session=db, ...)
   # After
   return await _summary_service(session=db, ...)
   ```

Route handlers are already `async def` — no signature change needed.

**Acceptance:**
- [ ] All 6 route handlers use `AsyncSession` in dependency
- [ ] All service calls are `await`ed
- [ ] Import updated: `AsyncSession` from `sqlalchemy.ext.asyncio`

---

### P1.3.8 — Update `app/api/routes/conversations.py`

Same pattern as P1.3.7 for 2 endpoints:
- `list_conversations_endpoint`
- `get_conversation_messages_endpoint`

**Acceptance:**
- [ ] Both handlers use `AsyncSession`
- [ ] Both service calls are `await`ed

---

### P1.3.9 — Update `app/main.py` lifespan

**Current:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_database(settings.database_url)
    check_database_connection()
    app.state.settings = settings
    try:
        yield
    finally:
        close_database()
```

**Target:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_database(settings.database_url)
    await check_database_connection()
    app.state.settings = settings
    try:
        yield
    finally:
        await close_database()
```

Only two lines change: `await` added to `check_database_connection()` and `close_database()`.

**Acceptance:**
- [ ] `check_database_connection()` is awaited
- [ ] `close_database()` is awaited
- [ ] App starts without errors

---

### P1.3.10 — Smoke Test

**Steps:**
```powershell
# Start the app (requires valid DATABASE_URL)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Verify health endpoint
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# Quick endpoint check
curl "http://localhost:8000/api/v1/analytics/summary"
# Expected: JSON response with analytics summary
```

**Acceptance:**
- [ ] App starts, connects to DB, logs no errors
- [ ] `/health` returns 200
- [ ] At least one analytics endpoint returns valid JSON

---

## Execution Order

All tasks are **sequential** (Gate-only, no parallel streams):

```text
P1.3.1 (requirements)
  └─ P1.3.2 (database.py)
       ├─ P1.3.3 (deps.py)
       │    ├─ P1.3.5 (analytics service)
       │    │    └─ P1.3.7 (analytics routes)
       │    └─ P1.3.6 (conversations service)
       │         └─ P1.3.8 (conversations routes)
       ├─ P1.3.4 (__init__.py)
       └─ P1.3.9 (main.py lifespan)
                     └─ P1.3.10 (smoke-test)
```

Critical path: `P1.3.1 → P1.3.2 → P1.3.3 → P1.3.5 → P1.3.7 → P1.3.10`

## Definition of Done (Phase 3)
- [ ] All database access uses `AsyncSession` via `create_async_engine` + `asyncpg`.
- [ ] No sync `Session`, `create_engine`, or `sessionmaker` imports remain in application code.
- [ ] All service functions are `async def` with `await session.execute(...)`.
- [ ] All route handlers `await` their service calls.
- [ ] App starts successfully with `uvicorn` and `/health` returns 200.
- [ ] Alembic migrations still work (sync driver preserved for Alembic).

## Risk Notes
- **Breaking change**: The app cannot run in a hybrid state. All 10 tasks must be completed atomically before the app functions again.
- **Lazy loading**: `AsyncSession` does not support lazy relationship loading. Not a concern here since no relationships are loaded in queries.
- **Alembic compatibility**: Alembic uses its own sync engine via `env.py`. The `DATABASE_URL` stays `postgresql://` in `.env`; only the app runtime swaps to `postgresql+asyncpg://`.
