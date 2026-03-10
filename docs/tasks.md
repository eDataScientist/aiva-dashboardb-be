# Tasks Checklist

## Milestone 1: FastAPI Analytics Backend Foundation
Status: `IN REVIEW`  
Last Updated: `2026-03-02` (Post-completion Stream A review: `P1.2.2` approved; `P1.2.3` kept in review for no-data contract mismatch)

## Phase 1 - Gate 1.0 (Foundation)
- [x] `P1.1.1 - Design - Audit source schemas and column semantics - Gate (Independent)`
- [x] `P1.1.2 - Design - Define SQLAlchemy 2.0 model contract - Gate (Dependent)` (`P1.1.1`)
- [x] `P1.1.3 - Design - Define enum and normalization strategy - Gate (Dependent)` (`P1.1.2`)
- [x] `P1.1.4 - DB - Initialize Alembic environment and target metadata - Gate (Dependent)` (`P1.1.2`)
- [x] `P1.1.5 - DB - Create baseline migration for current schema - Gate (Dependent)` (`P1.1.4`)
- [x] `P1.1.6 - DB - Add extension migration for analytics schema and indexes - Gate (Dependent)` (`P1.1.5`)
- [x] `P1.1.7 - Infra - Scaffold FastAPI project structure and dependency set - Gate (Dependent)` (`P1.1.4`)
- [x] `P1.1.8 - Config - Implement settings and DB lifecycle hooks - Gate (Dependent)` (`P1.1.7`)

## Phase 2 - Gate 2.0 + Streams (Analytics + Conversations API)
## Gate 2.0
- [x] `P1.2.1 - API - Define analytics and conversations request/response schemas - Gate (Dependent)` (`P1.1.8`)

## Stream A
- [x] `P1.2.2 - API - Implement summary endpoint aggregates - Stream A (Dependent)` (`P1.2.1`) - `DONE`
- [ ] `P1.2.3 - API - Implement message volume trend endpoint - Stream A (Dependent)` (`P1.2.1`) - `IN REVIEW` (contract mismatch: no-data behavior)

## Stream B
- [x] `P1.2.4 - API - Implement top intents endpoint - Stream B (Dependent)` (`P1.2.1`)
- [x] `P1.2.5 - API - Implement peak hours endpoint - Stream B (Dependent)` (`P1.2.1`)

## Stream C
- [x] `P1.2.6 - API - Implement quality trend endpoint - Stream C (Dependent)` (`P1.2.1`, `P1.1.6`)
- [x] `P1.2.7 - API - Implement lead conversion trend endpoint - Stream C (Dependent)` (`P1.2.1`)
- [x] `P1.2.8 - API - Add OpenAPI examples for Phase 2 endpoints - Stream C (Dependent)` (`P1.2.2`, `P1.2.4`, `P1.2.6`, `P1.2.9`, `P1.2.10`)

## Stream D
- [x] `P1.2.9 - API - Implement conversations list endpoint - Stream D (Dependent)` (`P1.2.1`)
- [x] `P1.2.10 - API - Implement conversation messages endpoint - Stream D (Dependent)` (`P1.2.1`, `P1.2.9`)

## Phase 3 - Gate 3.0 (Async Database Migration)
- [x] `P1.3.1 - Infra - Add asyncpg dependency - Gate (Dependent)` (`P1.2.10`)
- [x] `P1.3.2 - DB - Rewrite database.py to create_async_engine + async_sessionmaker - Gate (Dependent)` (`P1.3.1`)
- [x] `P1.3.3 - DB - Rewrite deps.py to async AsyncSession dependency - Gate (Dependent)` (`P1.3.2`)
- [x] `P1.3.4 - DB - Update db __init__.py exports - Gate (Dependent)` (`P1.3.2`)
- [x] `P1.3.5 - API - Convert analytics service to async - Gate (Dependent)` (`P1.3.3`)
- [x] `P1.3.6 - API - Convert conversations service to async - Gate (Dependent)` (`P1.3.3`)
- [x] `P1.3.7 - API - Update analytics routes for AsyncSession + await - Gate (Dependent)` (`P1.3.5`)
- [x] `P1.3.8 - API - Update conversations routes for AsyncSession + await - Gate (Dependent)` (`P1.3.6`)
- [x] `P1.3.9 - Infra - Update main.py lifespan to async - Gate (Dependent)` (`P1.3.2`)
- [x] `P1.3.10 - QA - Smoke-test app starts and /health returns 200 - Gate (Dependent)` (`P1.3.7`, `P1.3.8`, `P1.3.9`)

## Phase 4 - Gate 4.0 (ORM Query Rewrite)
- [x] `P1.4.1 - API - Rewrite get_analytics_summary to ORM - Gate (Dependent)` (`P1.3.10`)
- [x] `P1.4.2 - API - Rewrite get_message_volume_trend to ORM - Gate (Dependent)` (`P1.3.10`)
- [x] `P1.4.3 - API - Rewrite get_top_intents to ORM - Gate (Dependent)` (`P1.3.10`)
- [x] `P1.4.4 - API - Rewrite get_peak_hours to ORM + Python zero-fill - Gate (Dependent)` (`P1.3.10`)
- [x] `P1.4.5 - API - Remove dead raw-SQL helpers and string constants - Gate (Dependent)` (`P1.4.1`, `P1.4.2`, `P1.4.3`, `P1.4.4`)
- [x] `P1.4.6 - QA - Spot-check endpoints return same results - Gate (Dependent)` (`P1.4.5`)

## Phase 5 - Gate 5.0 (Test Environment)
- [x] `P1.5.1 - Infra - Add test deps (pytest, httpx, testcontainers) - Gate (Dependent)` (`P1.4.6`)
- [x] `P1.5.2 - Infra - Create pytest.ini - Gate (Dependent)` (`P1.5.1`)
- [x] `P1.5.3 - Test - Create tests/conftest.py with Testcontainers PG lifecycle - Gate (Dependent)` (`P1.5.2`)
- [x] `P1.5.4 - Test - Create tests/test_health.py - Gate (Dependent)` (`P1.5.3`)
- [x] `P1.5.5 - Test - Create tests/test_enums.py - Gate (Independent)` (`P1.5.2`)

## Stream A (Analytics Tests)
- [x] `P1.5.A.1 - Test - Test analytics service layer (Happy Path) - Stream A (Dependent)` (`Gate 5.0`)
- [x] `P1.5.A.2 - Test - Test analytics service layer (Edge Cases) - Stream A (Dependent)` (`P1.5.A.1`)
- [x] `P1.5.A.3 - Test - Test analytics API routes via httpx (Happy Path) - Stream A (Dependent)` (`P1.5.A.1`)
- [x] `P1.5.A.4 - Test - Test analytics API routes via httpx (Edge Cases) - Stream A (Dependent)` (`P1.5.A.3`)

## Stream B (Conversations Tests)
- [x] `P1.5.B.1 - Test - Test conversations service layer (Happy Path) - Stream B (Dependent)` (`Gate 5.0`)
- [x] `P1.5.B.2 - Test - Test conversations service layer (Edge Cases) - Stream B (Dependent)` (`P1.5.B.1`)
- [x] `P1.5.B.3 - Test - Test conversations API routes via httpx (Happy Path) - Stream B (Dependent)` (`P1.5.B.1`)
- [x] `P1.5.B.4 - Test - Test conversations API routes via httpx (Edge Cases) - Stream B (Dependent)` (`P1.5.B.3`)

## Gate 5.5 - QA Verification
- [x] `P1.5.C.1 - QA - Run full pytest suite and verify all tests pass - QA (Dependent)` (`Stream A`, `Stream B`)

## Milestone 2: AI Grading, Monitoring, and Access Foundations
Status: `IN PROGRESS`  
Last Updated: `2026-03-09` (Inserted Phase 3.5 prompt externalization plan before Phase 4 execution)

## Phase 1 - Gate 1.0 (Shared Milestone 2 Data Contracts)
- [x] `P2.1.1 - Design - Finalize customer-day grade grain and canonical identity contract - Gate (Independent)`
- [x] `P2.1.2 - Design - Finalize intent taxonomy codes/labels map for Milestone 2 - Gate (Dependent)` (`P2.1.1`)
- [x] `P2.1.3 - Design - Define configurable highlight-rules data contract and compute-on-read policy - Gate (Dependent)` (`P2.1.1`)
- [x] `P2.1.4 - Design - Define auth account/profile schema contract and security constraints - Gate (Dependent)` (`P2.1.1`)

## Stream A (`conversation_grades` Contract + ORM Updates)
- [x] `P2.1.5 - DB - Update conversation_grades ORM model for Milestone 2 fields - Stream A (Dependent)` (`P2.1.4`) - `DONE`
- [x] `P2.1.6 - DB - Add Alembic migration for conversation_grades Milestone 2 contract changes - Stream A (Dependent)` (`P2.1.5`) - `DONE`
- [x] `P2.1.7 - QA - Validate conversation_grades migration upgrade/downgrade behavior - Stream A (Dependent)` (`P2.1.6`) - `DONE`

## Stream B (Highlight Rules Configuration Schema)
- [x] `P2.1.8 - DB - Add highlight rules configuration ORM model - Stream B (Dependent)` (`P2.1.3`)
- [x] `P2.1.9 - DB - Add Alembic migration and default seed strategy for highlight rules config - Stream B (Dependent)` (`P2.1.8`)
- [x] `P2.1.10 - Design - Define shared highlight codes and response-facing labels contract - Stream B (Dependent)` (`P2.1.3`)

## Stream C (Auth and Account Data Model + Migration)
- [x] `P2.1.11 - DB - Add account ORM model (auth + minimal profile columns) - Stream C (Dependent)` (`P2.1.4`) - `DONE`
- [x] `P2.1.12 - DB - Add Alembic migration for account table and role constraints/indexes - Stream C (Dependent)` (`P2.1.11`) - `DONE`
- [x] `P2.1.13 - QA - Validate account migration constraints and uniqueness rules - Stream C (Dependent)` (`P2.1.12`) - `DONE`

## Stream D (Shared Contracts and Phase Validation)
- [x] `P2.1.14 - API - Define shared schema/constants contracts for downstream Milestone 2 phases - Stream D (Dependent)` (`P2.1.2`, `P2.1.3`, `P2.1.4`) - `DONE`
- [x] `P2.1.15 - QA - Run compile and migration smoke checks for Phase 1 changes - Stream D (Dependent)` (`P2.1.7`, `P2.1.9`, `P2.1.13`, `P2.1.14`) - `DONE`

## Phase 2 - Gate 2.0 (Auth Core Contract and Security Primitives)
- [x] `P2.2.1 - Design - Finalize auth transport, token claims, and route access matrix - Gate (Independent)` - `DONE`
- [x] `P2.2.2 - DB - Validate account schema readiness and add additive migration if gaps exist - Gate (Dependent)` (`P2.2.1`) - `DONE` (no additive migration required)
- [x] `P2.2.3 - Config - Add auth settings contract and validation rules - Gate (Dependent)` (`P2.2.1`) - `DONE`
- [x] `P2.2.4 - API - Define auth and account profile schemas plus auth error payloads - Gate (Dependent)` (`P2.2.1`) - `DONE`
- [x] `P2.2.5 - Service - Implement password hashing/token utilities and current-account dependency primitives - Gate (Dependent)` (`P2.2.2`, `P2.2.3`, `P2.2.4`) - `DONE`

## Stream A (Authentication Endpoints)
- [x] `P2.2.6 - Service - Implement account authentication flow with active-account checks - Stream A (Dependent)` (`P2.2.5`) - `DONE`
- [x] `P2.2.7 - API - Add login endpoint issuing access tokens and account context - Stream A (Dependent)` (`P2.2.6`) - `DONE`
- [x] `P2.2.8 - API - Add authenticated identity endpoint for current account context - Stream A (Dependent)` (`P2.2.7`) - `DONE`
- [x] `P2.2.9 - Test - Add auth service and route tests for success and failure paths - Stream A (Dependent)` (`P2.2.8`) - `DONE` (compile passed; `pytest tests/test_auth_service.py tests/test_auth_api.py -q` passed outside sandbox)

## Stream B (Account Profile Endpoints)
- [x] `P2.2.10 - Service - Implement authenticated profile read/update service - Stream B (Dependent)` (`P2.2.5`) - `DONE`
- [x] `P2.2.11 - API - Add account profile endpoints (GET/PATCH /api/v1/accounts/me) - Stream B (Dependent)` (`P2.2.10`) - `DONE`
- [x] `P2.2.12 - Test - Add profile API tests for validation and permissions - Stream B (Dependent)` (`P2.2.11`) - `DONE` (covered by targeted auth/profile/guard verification suite: `30 passed` outside sandbox)

## Stream C (Protected Routing and Access Baseline)
- [x] `P2.2.13 - Design - Finalize baseline role guard policy for Milestone 2 routes - Stream C (Independent)` (`P2.2.1`) - `DONE` (policy documented in m2-phase-2.md)
- [x] `P2.2.14 - API - Apply auth guards to protected route groups and register auth router - Stream C (Dependent)` (`P2.2.5`, `P2.2.13`) - `DONE` (analytics + conversations routes guarded)
- [x] `P2.2.15 - Test - Add authorization tests for protected route behavior - Stream C (Dependent)` (`P2.2.14`) - `DONE` (tests/test_authz_guards.py created; compile passed; `pytest tests/test_authz_guards.py -q` passed outside sandbox)

## Stream D (Phase Validation and Handoff)
- [x] `P2.2.16 - QA - Run compile and targeted pytest verification for Phase 2 auth scope - Stream D (Dependent)` (`P2.2.9`, `P2.2.12`, `P2.2.15`) - `DONE` (compile passed; targeted auth/profile/guard suites passed outside sandbox: `30 passed`)
- [x] `P2.2.17 - Docs - Update task/progress docs with Phase 2 execution notes and residual risks - Stream D (Dependent)` (`P2.2.16`) - `DONE` (tasks/progress/phase docs synchronized with Stream D execution outcomes)

## Phase 3 - Gate 3.0 (AI Grading Pipeline Core)
## Gate 3.0
- [x] `P2.3.1 - Design - Finalize grading rubric/output contract and parse-failure policy - Gate (Independent)` - `DONE`
- [x] `P2.3.2 - DB - Validate conversation_grades write constraints and add additive migration if gaps exist - Gate (Dependent)` (`P2.3.1`) - `DONE`
- [x] `P2.3.3 - Config - Add grading provider/model settings contract and validation - Gate (Dependent)` (`P2.3.1`) - `DONE`
- [x] `P2.3.4 - API - Define internal grading schemas and parser error contract - Gate (Dependent)` (`P2.3.1`) - `DONE`
- [x] `P2.3.5 - Service - Scaffold grading module boundaries and shared customer-day selectors - Gate (Dependent)` (`P2.3.2`, `P2.3.4`) - `DONE`

## Stream A (Customer-Day Extraction and Transcript Assembly)
- [x] `P2.3.6 - Service - Implement customer-day candidate selection and canonical identity grouping - Stream A (Dependent)` (`P2.3.5`) - `DONE`
- [x] `P2.3.7 - Service - Implement transcript assembly/normalization for one customer-day - Stream A (Dependent)` (`P2.3.6`) - `DONE`
- [x] `P2.3.8 - Test - Add deterministic extraction/normalization fixtures and coverage - Stream A (Dependent)` (`P2.3.7`) - `DONE` (`tests/test_grading_extraction.py` added; targeted pytest passed outside sandbox: `3 passed`)

## Stream B (Prompting, Provider Adapter, and Parse Validation)
- [x] `P2.3.9 - Service - Implement grading prompt builder with rubric and intent taxonomy injection - Stream B (Dependent)` (`P2.3.4`) - `DONE`
- [x] `P2.3.10 - Service - Implement AI grader adapter plus strict parse/validation flow - Stream B (Dependent)` (`P2.3.3`, `P2.3.9`) - `DONE` (rereview approved after fixing the default `mock` provider path and verifying real prompt-builder -> provider -> parser execution)
- [x] `P2.3.11 - Test - Add prompt/parser contract tests with mocked provider responses - Stream B (Dependent)` (`P2.3.10`) - `DONE` (rereview approved after adding regression coverage for the real `build_grading_prompt()` -> default-`mock`-provider -> `parse_grading_output()` path)

## Stream C (Persistence and Core Orchestration)
- [x] `P2.3.12 - Service - Implement conversation_grades upsert persistence for one customer-day - Stream C (Dependent)` (`P2.3.2`, `P2.3.4`) - `DONE` (review approved; `app/services/grading_persistence.py`, `tests/test_grading_pipeline.py`)
- [x] `P2.3.13 - Service - Implement grade_customer_day orchestration (extract -> grade -> persist) - Stream C (Dependent)` (`P2.3.8`, `P2.3.11`, `P2.3.12`) - `DONE` (rereview approved after explicit success/failure result contract and empty-transcript short-circuit were added; targeted pytest passed: `7 passed`)
- [x] `P2.3.14 - Test - Add grading pipeline service tests for idempotent reruns and partial-failure behavior - Stream C (Dependent)` (`P2.3.13`) - `DONE` (rereview approved after failure-result assertions and empty-transcript coverage were added; targeted pytest passed: `7 passed`)

## Stream D (Phase Validation and Handoff)
- [x] `P2.3.15 - QA - Run compile and targeted pytest verification for grading pipeline scope - Stream D (Dependent)` (`P2.3.14`) - `DONE` (compile passed; sandboxed grading pytest hit the expected Docker npipe blocker; unrestricted targeted grading suite passed: `31 passed`)
- [x] `P2.3.16 - Docs - Update task/progress docs with Phase 3 execution notes and Phase 4 handoff risks - Stream D (Dependent)` (`P2.3.15`) - `DONE` (`docs/tasks.md`, `docs/project-progress.md`, and `docs/milestone-2/m2-phase-3.md` synchronized with Stream D execution notes and Phase 4 handoff risks)

## Phase 3.5 - Prompt Externalization and Legacy Multi-Prompt Alignment
## Gate 3.5
- [x] `P2.35.1 - Design - Finalize prompt-pack contract, legacy parity scope, and merge strategy - Gate (Independent)` - `DONE` (`docs/milestone-2/m2-phase-3.5.md`, `docs/milestone-2/milestone-notes.md`)
- [x] `P2.35.2 - DB - Validate that no migration is required for prompt externalization scope - Gate (Dependent)` (`P2.35.1`) - `DONE` (`docs/milestone-2/m2-phase-3.5.md`, `docs/milestone-2/milestone-notes.md`)
- [x] `P2.35.3 - Config - Add prompt-pack settings and validation contract - Gate (Dependent)` (`P2.35.1`) - `DONE` (`app/core/config.py`, `app/core/constants.py`, `app/core/__init__.py`, `.env.example`, `app/prompt_assets/grading/v1/*`, `tests/test_grading_config.py`)
- [x] `P2.35.4 - API - Define internal prompt-spec and partial-output schemas - Gate (Dependent)` (`P2.35.1`) - `DONE` (`app/schemas/grading_prompts.py`, `app/schemas/__init__.py`, `tests/test_grading_schemas.py`)
- [x] `P2.35.5 - Service - Scaffold prompt-pack loader and multi-prompt orchestration module boundaries - Gate (Dependent)` (`P2.35.3`, `P2.35.4`) - `DONE` (`app/services/grading_prompt_assets.py`, `app/services/grading_prompt.py`, `app/services/grading_provider.py`, `app/services/__init__.py`, `tests/test_grading_prompt.py`)

## Stream A (Prompt Assets and File Loader)
- [ ] `P2.35.6 - Service - Externalize grading prompts into versioned markdown prompt-pack assets - Stream A (Dependent)` (`P2.35.5`)
- [ ] `P2.35.7 - Service - Implement prompt-pack file loader with shared system-prompt injection rules - Stream A (Dependent)` (`P2.35.6`)
- [ ] `P2.35.8 - Test - Add prompt-pack loader and asset integrity tests - Stream A (Dependent)` (`P2.35.7`)

## Stream B (Multi-Prompt Build, Parse, and Canonical Merge)
- [ ] `P2.35.9 - Service - Implement per-domain prompt bundle generation aligned to legacy 5-prompt flow - Stream B (Dependent)` (`P2.35.7`)
- [ ] `P2.35.10 - Service - Implement partial-result parsing and canonical GradingOutput merge - Stream B (Dependent)` (`P2.35.4`, `P2.35.9`)
- [ ] `P2.35.11 - Test - Add deterministic multi-prompt parse and merge contract tests - Stream B (Dependent)` (`P2.35.10`)

## Stream C (Pipeline Integration and Runtime Compatibility)
- [ ] `P2.35.12 - Service - Integrate file-based multi-prompt execution into grade_customer_day orchestration - Stream C (Dependent)` (`P2.35.10`)
- [ ] `P2.35.13 - Service - Update provider and mock runtime contracts for prompt-pack execution - Stream C (Dependent)` (`P2.35.12`)
- [ ] `P2.35.14 - Test - Add end-to-end grading pipeline tests for file-based multi-prompt execution - Stream C (Dependent)` (`P2.35.13`)

## Stream D (Validation, Docs, and Phase 4 Handoff)
- [ ] `P2.35.15 - QA - Run compile and targeted pytest verification for prompt-pack refactor scope - Stream D (Dependent)` (`P2.35.11`, `P2.35.14`)
- [ ] `P2.35.16 - Docs - Update task/progress docs and Phase 4 dependency notes after prompt refactor - Stream D (Dependent)` (`P2.35.15`)

## Phase 4 - Gate 4.0 (Batch Execution and Run Management)
Phase dependency note: execution is deferred until Phase 3.5 prompt externalization completes.

## Gate 4.0
- [ ] `P2.4.1 - Design - Finalize batch run contract, statuses, idempotency, and access matrix - Gate (Independent)`
- [ ] `P2.4.2 - DB - Add grading run and run-item schema for durable history - Gate (Dependent)` (`P2.4.1`)
- [ ] `P2.4.3 - Config - Add batch execution and scheduler settings contract - Gate (Dependent)` (`P2.4.1`)
- [ ] `P2.4.4 - API - Define grading run trigger/history schemas and error payloads - Gate (Dependent)` (`P2.4.1`)
- [ ] `P2.4.5 - Service - Scaffold grading batch execution and run-tracking module boundaries - Gate (Dependent)` (`P2.4.2`, `P2.4.4`)

## Stream A (Run Ledger Persistence)
- [ ] `P2.4.6 - Service - Implement grading run lifecycle persistence and status transitions - Stream A (Dependent)` (`P2.4.5`)
- [ ] `P2.4.7 - Service - Implement run-item result recording and aggregated counters - Stream A (Dependent)` (`P2.4.6`)
- [ ] `P2.4.8 - Test - Add deterministic run-ledger persistence tests - Stream A (Dependent)` (`P2.4.7`)

## Stream B (Batch Executor and Idempotent Date Windows)
- [ ] `P2.4.9 - Service - Implement date-window planning with scheduled/manual skip-rerun policy - Stream B (Dependent)` (`P2.4.5`)
- [ ] `P2.4.10 - Service - Implement batch executor over customer-day candidates with advisory locking - Stream B (Dependent)` (`P2.4.7`, `P2.4.9`)
- [ ] `P2.4.11 - Test - Add batch executor tests for scheduled, rerun, and mixed-failure runs - Stream B (Dependent)` (`P2.4.10`)

## Stream C (Manual Trigger and Run History API)
- [ ] `P2.4.12 - Service - Implement manual run trigger/list/detail service wrappers and access checks - Stream C (Dependent)` (`P2.4.4`, `P2.4.10`)
- [ ] `P2.4.13 - API - Add protected grading run trigger and history endpoints - Stream C (Dependent)` (`P2.4.12`)
- [ ] `P2.4.14 - Test - Add grading run API tests for auth, validation, and history payloads - Stream C (Dependent)` (`P2.4.13`)

## Stream D (Daily Scheduling, Phase Validation, and Handoff)
- [ ] `P2.4.15 - Infra - Add previous-day scheduler hook and stale-run recovery path - Stream D (Dependent)` (`P2.4.10`)
- [ ] `P2.4.16 - QA - Run compile and targeted pytest verification for batch/run-management scope - Stream D (Dependent)` (`P2.4.11`, `P2.4.14`, `P2.4.15`)
- [ ] `P2.4.17 - Docs - Update task/progress docs with Phase 4 execution notes and Phase 5/6 handoff risks - Stream D (Dependent)` (`P2.4.16`)
