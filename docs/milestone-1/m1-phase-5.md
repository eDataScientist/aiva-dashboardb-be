# Milestone 1 - Phase 5 Plan: Testing Infrastructure

## Goals
- Establish a robust, automated testing infrastructure using `pytest`, `pytest-asyncio`, and `httpx`.
- Use `testcontainers-python` to spin up ephemeral PostgreSQL databases for reliable, isolated integration tests.
- Achieve solid test coverage across both services and API routes (analytics and conversations).
- Ensure testing incorporates both standard "happy path" behavior and critical edge cases (validation faults, empty states).

## Dependencies
- Phase 4 is complete and all ORM queries are functional.

## Gate 5.0 - Test Environment Foundation
These tasks initialize the test environments, dependencies, and core configuration. They must complete before any parallel test streams begin to ensure the test app and database boot correctly.

| Task ID | Title | Type | Dependencies | Output |
|---|---|---|---|---|
| P1.5.1 | Add test deps (`pytest`, `pytest-asyncio`, `httpx`, `testcontainers`) | Infra | P1.4.6 | Updated `requirements.txt` |
| P1.5.2 | Create `pytest.ini` with pytest-asyncio settings | Infra | P1.5.1 | `pytest.ini` created |
| P1.5.3 | Create `tests/conftest.py` with Testcontainers PG lifecycle & async session | Test | P1.5.2 | `conftest.py` with DB fixtures |
| P1.5.4 | Health Check Test (`test_health.py`) | Test | P1.5.3 | Base API testing framework verified |
| P1.5.5 | Enum Validation Tests (`test_enums.py`) | Test | P1.5.2 | Independent enum tests pass |

## Stream A - Analytics Tests
These tests validate the ORM analytics and aggregations. Includes testing both the service layer and the HTTP boundary.

| Task ID | Title | Type | Dependencies | Output |
|---|---|---|---|---|
| P1.5.A.1 | Test `analytics` service layer (Happy Path) | Test | Gate 5.0 | Core service tests |
| P1.5.A.2 | Test `analytics` service layer (Edge Cases/Empty DB/Error states) | Test | P1.5.A.1 | Extended service tests |
| P1.5.A.3 | Test `analytics` API routes via httpx (Happy Path) | Test | P1.5.A.1 | Route API tests pass |
| P1.5.A.4 | Test `analytics` API routes via httpx (Edge/Validation Errors) | Test | P1.5.A.3 | Route API tests robust |

## Stream B - Conversations Tests
These tests validate the paginated messages and conversation retrieval functionalities. Includes testing both the service layer and the HTTP boundary.

| Task ID | Title | Type | Dependencies | Output |
|---|---|---|---|---|
| P1.5.B.1 | Test `conversations` service layer (Happy Path) | Test | Gate 5.0 | Core service tests |
| P1.5.B.2 | Test `conversations` service layer (Edge/Pagination/Filtering logic) | Test | P1.5.B.1 | Extended service tests |
| P1.5.B.3 | Test `conversations` API routes via httpx (Happy Path) | Test | P1.5.B.1 | Route API tests pass |
| P1.5.B.4 | Test `conversations` API routes via httpx (Edge/Validation Errors) | Test | P1.5.B.3 | Route API tests robust |

## Gate 5.5 - QA and Verification
| Task ID | Title | Type | Dependencies | Output |
|---|---|---|---|---|
| P1.5.C.1 | QA - Run full pytest suite and verify all tests pass | QA | Stream A, B | 100% pass rate in CI/Local |

## Parallelization Map
```
Gate 5.0 (Test Environment) ────┐
    │                           │
    ├── Stream A (Analytics) ───►│
    │                           │
    ├── Stream B (Convos) ──────►│  (parallel with A)
    │                           │
    │                           ▼
    └── Gate 5.5 (QA) ──────────► Phase Complete
```

## Definition of Done
- `Testcontainers` successfully spins up Postgres, applies the alembic migrations, and tears down cleanly.
- `AsyncSession` is yielded correctly to each test function, rolling back changes after each test.
- Analytics unit/integration tests successfully cover the zero-fill python merge logic.
- Both `200 OK` outputs and `4xx` Validation error edge-cases are accounted for in both streams.
- Running `pytest` successfully completes with no errors or lingering connections.

## Test Scenarios
### Happy Path
- Basic summaries calculate correctly given populated database.
- Pagination attributes return accurate values for given offset and limit thresholds.
- Date boundary filtering logic isolates rows properly.
### Edge Cases
- No rows in DB → Summary fields return `0` or empty dicts as applicable appropriately.
- Start date after End date → Validation error `400 Bad Request`.
- Invalid ENUM values inside the query parameters.

## Open Questions and Assumptions
- Assuming `testcontainers-python` works seamlessly with your local Docker Daemon context. It will need the Docker Engine to be running during tests.

## Estimated Duration
- Gate 5.0: ~1.5 Units (Test framework setup usually has teething issues)
- Stream A: ~1.0 Units
- Stream B: ~1.0 Units
- Total Parallel Duration: ~3.0 Units
