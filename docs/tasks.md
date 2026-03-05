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
Last Updated: `2026-03-04` (Stream D review completed: `P2.1.14` and `P2.1.15` moved to `DONE`; Phase 1 complete)

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
