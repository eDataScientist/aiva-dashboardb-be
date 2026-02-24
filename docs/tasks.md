# Tasks Checklist

## Milestone 1: FastAPI Analytics Backend Foundation
Status: `DONE`  
Last Updated: `2026-02-24` (Phase 5 complete: Stream B and Gate 5.5 verified; full pytest suite passing)

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
- [x] `P1.2.2 - API - Implement summary endpoint aggregates - Stream A (Dependent)` (`P1.2.1`)
- [x] `P1.2.3 - API - Implement message volume trend endpoint - Stream A (Dependent)` (`P1.2.1`)

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
