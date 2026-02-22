# Tasks Checklist

## Milestone 1: FastAPI Analytics Backend Foundation
Status: `IN PROGRESS`  
Last Updated: `2026-02-21`

## Phase 1 - Gate 1.0 (Foundation)
- [x] `P1.1.1 - Design - Audit source schemas and column semantics - Gate (Independent)`
- [x] `P1.1.2 - Design - Define SQLAlchemy 2.0 model contract - Gate (Dependent)` (`P1.1.1`)
- [x] `P1.1.3 - Design - Define enum and normalization strategy - Gate (Dependent)` (`P1.1.2`)
- [x] `P1.1.4 - DB - Initialize Alembic environment and target metadata - Gate (Dependent)` (`P1.1.2`)
- [x] `P1.1.5 - DB - Create baseline migration for current schema - Gate (Dependent)` (`P1.1.4`)
- [x] `P1.1.6 - DB - Add extension migration for analytics schema and indexes - Gate (Dependent)` (`P1.1.5`)
- [x] `P1.1.7 - Infra - Scaffold FastAPI project structure and dependency set - Gate (Dependent)` (`P1.1.4`)
- [x] `P1.1.8 - Config - Implement settings and DB lifecycle hooks - Gate (Dependent)` (`P1.1.7`)

## Phase 2 - Gate 2.0 + Streams (Analytics API)
## Gate 2.0
- [ ] `P1.2.1 - API - Define analytics request and response schemas - Gate (Dependent)` (`P1.1.8`)

## Stream A
- [ ] `P1.2.2 - API - Implement summary endpoint aggregates - Stream A (Dependent)` (`P1.2.1`)
- [ ] `P1.2.3 - API - Implement message volume trend endpoint - Stream A (Dependent)` (`P1.2.1`)

## Stream B
- [ ] `P1.2.4 - API - Implement top intents endpoint - Stream B (Dependent)` (`P1.2.1`)
- [ ] `P1.2.5 - API - Implement peak hours endpoint - Stream B (Dependent)` (`P1.2.1`)

## Stream C
- [ ] `P1.2.6 - API - Implement quality trend endpoint - Stream C (Dependent)` (`P1.2.1`, `P1.1.6`)
- [ ] `P1.2.7 - API - Implement lead conversion trend endpoint - Stream C (Dependent)` (`P1.2.1`)
- [ ] `P1.2.8 - API - Add OpenAPI examples for analytics endpoints - Stream C (Dependent)` (`P1.2.2`, `P1.2.4`, `P1.2.6`)

## Phase 3 - Gate 3.0 (Validation and Handoff)
- [ ] `P1.3.1 - QA - Run python compile checks on modified modules - Gate (Dependent)` (`P1.2.3`, `P1.2.5`, `P1.2.8`)
- [ ] `P1.3.2 - QA - Run lint checks and resolve violations - Gate (Dependent)` (`P1.3.1`)
- [ ] `P1.3.3 - QA - Verify migration upgrade and downgrade path - Gate (Dependent)` (`P1.3.1`)
- [ ] `P1.3.4 - QA - Execute endpoint smoke scenarios - Gate (Dependent)` (`P1.3.2`)
- [ ] `P1.3.5 - Docs - Publish runbook and handoff notes - Gate (Dependent)` (`P1.3.4`)
