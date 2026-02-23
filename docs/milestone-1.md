# Milestone 1 SRS: FastAPI Analytics Backend Foundation

## Purpose
Milestone 1 establishes the backend foundation for analytics by introducing:
- FastAPI service structure
- SQLAlchemy model layer
- `databases` async database access
- Alembic migration workflow
- Initial analytics endpoints

This document is intentionally high-level. Detailed execution is split into phase documents (starting with `docs/m1-phase-1.md`).

## Goals
- Create a runnable FastAPI backend with versioned API routes.
- Extend and normalize the current schema for analytics use cases.
- Provide MVP analytics read endpoints for dashboard consumption.
- Ensure migrations, code quality checks, and handoff readiness.

## Out of Scope
- Authentication/authorization
- Caching/background workers
- Advanced performance optimization/materialized views
- Full observability stack

## Phase Plan (Brief)

## Phase 1 - Foundation (Data + Migration + App Core)
Objective: Build the technical base required by all endpoint work.

Subtasks (brief):
- Audit current schema and finalize model contract.
- Define normalization strategy for enums/boolean-like fields.
- Initialize Alembic and add baseline + extension migrations.
- Scaffold FastAPI project structure and dependency wiring.
- Add environment configuration and DB lifecycle hooks.

Detailed plan: `docs/m1-phase-1.md`

## Phase 2 - Analytics API MVP
Objective: Deliver initial analytics endpoints for summary and trends.

Subtasks (brief):
- Define shared request/response contracts.
- Implement summary and volume trend endpoints.
- Implement top intents and peak-hours endpoints.
- Implement quality and lead-conversion trend endpoints.
- Add OpenAPI examples for frontend integration.

## Phase 3 - Async Database Migration
Objective: Port the synchronous SQLAlchemy `Session` layer to `AsyncSession` with `asyncpg`.

Subtasks (brief):
- Add `asyncpg` dependency.
- Rewrite `app/db/database.py` to use `create_async_engine` and `async_sessionmaker`.
- Update `app/db/deps.py` to yield `AsyncSession`.
- Convert all service functions to `async def` with `await session.execute(...)`.
- Update route handlers to `await` service calls.
- Update `app/main.py` lifespan for async connect/disconnect.

## Phase 4 - ORM Query Rewrite
Objective: Eliminate raw `text()` SQL in favour of SQLAlchemy ORM expressions.

Subtasks (brief):
- Rewrite `get_analytics_summary` using ORM `select()`, `func`, and `case()`.
- Rewrite `get_message_volume_trend` using ORM date bucketing.
- Rewrite `get_top_intents` using ORM with intent normalization.
- Rewrite `get_peak_hours` using ORM with Python-side zero-fill.
- Remove dead raw-SQL helper functions and string constants.

## Phase 5 - Testing Infrastructure
Objective: Build a comprehensive pytest test suite backed by Docker PostgreSQL.

Subtasks (brief):
- Add `pytest`, `pytest-asyncio`, `httpx`, `testcontainers[postgres]` dependencies.
- Create `tests/conftest.py` with Docker PG lifecycle, Alembic migrations, and seed data.
- Write unit tests for enum normalizers.
- Write service-level tests for all analytics and conversations functions.
- Write integration tests for all API endpoints via `httpx.AsyncClient`.

## Phase Dependencies
- `Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5`
- Phase 3 cannot start before Phase 2 completion.
- Phase 4 cannot start before Phase 3 completion.
- Phase 5 cannot start before Phase 4 completion.

## Milestone Deliverables
- FastAPI backend scaffold
- SQLAlchemy model definitions for current + extended schema
- Alembic migration setup and initial revisions
- Analytics API endpoints (MVP set)
- Async database layer (`AsyncSession` + `asyncpg`)
- Pure ORM query layer (no raw SQL)
- Pytest test suite with Docker PostgreSQL

## Success Criteria
- Service starts and exposes health + analytics routes.
- Migrations can upgrade and downgrade without errors.
- Endpoints return expected aggregate structures for date/channel filters.
- All database access is async (`AsyncSession`).
- No raw `text()` SQL in service layer.
- Full pytest suite passes against Docker PostgreSQL.
