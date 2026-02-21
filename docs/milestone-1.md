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

## Phase 3 - Validation and Handoff
Objective: Stabilize milestone output for review and continuation.

Subtasks (brief):
- Run compile/lint checks and resolve issues.
- Verify migration upgrade/downgrade reliability.
- Execute endpoint smoke tests (happy path + edge cases).
- Publish runbook and handoff notes.

## Phase Dependencies
- `Phase 1 -> Phase 2 -> Phase 3`
- Phase 2 cannot start before Phase 1 completion.
- Phase 3 cannot start before Phase 2 completion.

## Milestone Deliverables
- FastAPI backend scaffold
- SQLAlchemy model definitions for current + extended schema
- Alembic migration setup and initial revisions
- Analytics API endpoints (MVP set)
- Validation artifacts and runbook documentation

## Success Criteria
- Service starts and exposes health + analytics routes.
- Migrations can upgrade and downgrade without errors.
- Endpoints return expected aggregate structures for date/channel filters.
- Modified code passes compile and lint checks.
