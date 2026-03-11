# Milestone 2 - Phase 4 Plan: Batch Execution and Run Management

## Goals
- Operationalize the Phase 3 grading pipeline as a reusable batch runner for scheduled daily execution and bounded manual reruns/backfills.
- Add durable run-history tracking for each grading run and each customer-day attempt without changing raw chat/source tables.
- Preserve overwrite-safe grading semantics while preventing ambiguous duplicate/concurrent runs for the same target date window.
- Expose protected internal endpoints for manual run trigger and run-history inspection.
- Leave Phase 4 in a reviewable state with deterministic tests and clear handoff contracts for Phase 5 and Phase 6 consumers.

## Planning Analysis (Required Order)

### 1) Data Models
- Phase 3 already provides the core grading unit boundaries:
  - `list_customer_day_candidates(...)`
  - `grade_customer_day(...)`
  - explicit in-band result codes: `EMPTY_TRANSCRIPT`, `PROVIDER_ERROR`, `PARSE_ERROR`
  - overwrite-safe grade persistence keyed by canonical identity + GST `grade_date`
- Phase 4 should add durable batch-run storage rather than overloading `conversation_grades`:
  - `grading_runs` (one record per scheduled/manual run)
  - `grading_run_items` (one record per customer-day attempt within a run)
- Planning baseline for `grading_runs`:
  - `id`
  - `trigger_type` (`scheduled`, `manual`)
  - `run_mode` (`daily`, `backfill`, `rerun`)
  - `status` (`queued`, `running`, `completed`, `completed_with_failures`, `failed`)
  - `target_start_date`, `target_end_date`
  - `rerun_existing`
  - provider/runtime snapshot fields (`provider`, `model`, `prompt_version`)
  - aggregate counters (`candidate_count`, `success_count`, `empty_transcript_count`, `provider_error_count`, `parse_error_count`)
  - `requested_by_account_id` (nullable for scheduled runs)
  - `started_at`, `finished_at`, `created_at`, `updated_at`
- Planning baseline for `grading_run_items`:
  - `id`
  - `run_id`
  - candidate key fields (`identity_type`, `conversation_identity`, `grade_date`)
  - `status` / result code
  - optional `grade_id` reference for successful writes
  - bounded `error_message` / `error_details`
  - timestamps for attempt lifecycle
- Raw transcript content and raw provider output should not be stored in Phase 4 run-history tables by default; run history is for operations/debuggability, not transcript duplication.
- Batch-run identity remains canonical customer-day (`identity_type`, `conversation_identity`, `grade_date`) aligned with Phase 1/3 contracts.

### 2) Migration
- Phase 4 should be additive-only.
- New schema work is expected for:
  - `grading_runs`
  - `grading_run_items`
  - supporting indexes for run recency, status filters, and run-item lookups by run + candidate
- Raw chat/source tables remain untouched.
- `conversation_grades` should not require destructive change; if success-to-grade linkage is added, it should be additive and transition-safe.
- Concurrency protection should prefer application/runtime locking (for example PostgreSQL advisory locks keyed by target date window) over brittle overlapping partial-unique indexes on run states.
- Migration validation must include upgrade/downgrade smoke checks and confirm no impact on existing `conversation_grades` uniqueness behavior.

### 3) Dependencies
- Upstream dependencies satisfied:
  - Milestone 2 Phase 2 auth/account foundation
  - Milestone 2 Phase 3 grading extraction, provider, parser, persistence, and orchestration
- Phase 4 must consume, not replace, the Phase 3 orchestration contract:
  - batch execution must treat `EMPTY_TRANSCRIPT`, `PROVIDER_ERROR`, and `PARSE_ERROR` as expected controlled outcomes
  - run summaries and run-item rows should classify these outcomes explicitly
- Existing FastAPI lifespan wiring can host a daily scheduler hook, but there is no separate worker system in the current codebase.
- Provider/runtime dependency:
  - scheduled/manual non-test runs need a real provider configuration unless an explicit mock override is allowed
- Phase 5 and Phase 6 should depend on Phase 4 run-history contracts only for operational visibility, not for metric correctness.

### 4) Configuration
- Add explicit Phase 4 runtime settings and validation for:
  - daily scheduler enabled/disabled
  - previous-day run hour in `Asia/Dubai`
  - max manual backfill window (days)
  - stale-run timeout / recovery threshold
  - optional safety toggle controlling whether `GRADING_PROVIDER=mock` may execute non-test batch runs
- Phase 4 should fail safely when live/scheduled execution is enabled with an invalid provider/runtime configuration.
- Manual trigger validation should enforce bounded date windows and explicit rerun behavior rather than implicit broad backfills.
- Shared status/result-code constants should be centralized so service logic, API schemas, and tests cannot drift.

### 5) Endpoints
- Planned protected route group: `/api/v1/grading/runs/*`
- Planning baseline endpoints:
  - `POST /api/v1/grading/runs` - create a bounded manual run for one date or a date range
  - `GET /api/v1/grading/runs` - list recent runs with status/counter summaries and filters
  - `GET /api/v1/grading/runs/{run_id}` - retrieve one run with detailed counters and recent item/failure summary
  - optional follow-up if needed during Gate 4.0: `GET /api/v1/grading/runs/{run_id}/items`
- Access policy must be finalized in Gate 4.0.
- Planning baseline:
  - manual trigger requires an elevated role (default assumption: `super_admin`)
  - run-history read access is limited to elevated roles (default assumption: `super_admin` and possibly `company_admin`)
  - `analyst` access to run-management endpoints is out of scope unless Gate 4.0 decides otherwise

## Dependencies
- Phase dependency: `Milestone 2 Phase 3.5 complete -> Milestone 2 Phase 4`
- Downstream impact:
  - Phase 5 metrics APIs continue to read `conversation_grades` and may surface latest successful grading freshness, but should not depend on run-item internals for core aggregates.
  - Phase 6 monitoring APIs remain grade-data based, while Phase 4 provides the operational run ledger needed to explain freshness/failures.

## Upstream Note
- Phase 4 execution is intentionally downstream of the inserted Phase 3.5 prompt externalization/refactor.
- Phase 3.5 review completed on `2026-03-11`, validating the prompt-pack runtime with clean compile results plus targeted prompt/config/parser/pipeline coverage and confirming the remaining pipeline-suite blocker is sandbox-only Docker/Testcontainers access.
- Batch/run-management work should assume the validated file-based multi-prompt grading path from Phase 3.5, not the older single hardcoded prompt implementation.

## Phase 4 Contract Outline (Planning Baseline)

### Scheduled Daily Window
- Daily scheduled run targets the previous GST business day only.
- Scheduled runs should default to `rerun_existing = false` so the normal daily pass grades missing customer-days once.

### Manual Trigger Window
- Manual trigger supports either:
  - one explicit `grade_date`, or
  - a bounded `start_date` / `end_date`
- Manual trigger defaults to `rerun_existing = false`.
- Manual reruns/backfills may opt into `rerun_existing = true`, which relies on Phase 3 overwrite-safe upsert behavior.
- Pre-go-live retroactive backfill rules remain an explicit Gate 4.0 decision because the SRS still lists retroactive grading scope as open/deferred.

### Run Outcome Model
- Candidate-level outcomes:
  - `success`
  - `empty_transcript`
  - `provider_error`
  - `parse_error`
- Run-level statuses:
  - `queued`
  - `running`
  - `completed`
  - `completed_with_failures`
  - `failed`
- Mixed success/failure runs should normally end as `completed_with_failures`, not `failed`, unless the run itself aborts before candidate execution can finish meaningfully.

### Duplicate-Run Safety
- Phase 4 should prevent simultaneous execution of the same target window.
- Planning baseline: use a deterministic advisory-lock key derived from the target date window before a run transitions to `running`.
- Repeat execution after a prior run completes is allowed and must be visible as a new `grading_runs` record.

## Gate 4.0 - Batch Run Contract and Operational Safety

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 4.0.1 | `P2.4.1 - Design - Finalize batch run contract, statuses, idempotency, and access matrix - Gate (Independent)` | Lock the scheduled/manual run model, date-window rules, status/result vocabulary, duplicate-run safety, and elevated-access policy. | None | `docs/milestone-2/m2-phase-4.md`, `docs/milestone-2/milestone-notes.md` (if milestone-level decisions are updated) | Review checklist confirms run semantics are explicit and Phase 3 failure-result integration is unambiguous. |
| 4.0.2 | `P2.4.2 - DB - Add grading run and run-item schema for durable history - Gate (Dependent)` | Introduce additive tables/indexes for run summaries and per-candidate outcomes. | `P2.4.1` | `app/models/` (new run models), `alembic/versions/*.py` | Alembic upgrade/downgrade smoke; no destructive schema changes. |
| 4.0.3 | `P2.4.3 - Config - Add batch execution and scheduler settings contract - Gate (Dependent)` | Add and validate Phase 4 settings for scheduling, backfill bounds, stale-run handling, and live-provider safety. | `P2.4.1` | `app/core/config.py`, `app/core/__init__.py`, `.env.example` | Compile check and config validation tests for invalid/missing Phase 4 settings. |
| 4.0.4 | `P2.4.4 - API - Define grading run trigger/history schemas and error payloads - Gate (Dependent)` | Add typed request/response models for manual trigger, run list/detail, and run-item summaries. | `P2.4.1` | `app/schemas/grading_runs.py` (new), `app/schemas/__init__.py` | Schema validation tests and import/OpenAPI smoke checks. |
| 4.0.5 | `P2.4.5 - Service - Scaffold grading batch execution and run-tracking module boundaries - Gate (Dependent)` | Create service/module boundaries for run history, batch execution, trigger handling, and scheduling without circular imports. | `P2.4.2`, `P2.4.4` | `app/services/grading_runs.py` (new), `app/services/grading_batch.py` (new), `app/services/grading_scheduler.py` (new), `app/services/__init__.py` | Compile/import smoke ensures modules are discoverable and aligned to Phase 3 service boundaries. |

### Gate 4.0 Acceptance Criteria
- [ ] Batch run semantics and candidate/run status vocabulary are explicit and stable.
- [ ] Additive schema exists for durable run history and per-candidate outcome tracking.
- [ ] Scheduler/manual-trigger settings are validated at startup/config load.
- [ ] Typed schemas exist for manual trigger and run-history APIs.
- [ ] Service boundaries are established for run ledger, executor, and scheduler work.

## Stream A - Run Ledger Persistence

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.4.6 - Service - Implement grading run lifecycle persistence and status transitions - Stream A (Dependent)` | Persist run creation, `queued -> running -> terminal` transitions, runtime snapshot fields, and aggregate counters baseline. | `P2.4.5` | `app/services/grading_runs.py`, run models | Service tests for state transitions and invalid transition rejection. |
| A.2 | `P2.4.7 - Service - Implement run-item result recording and aggregated counters - Stream A (Dependent)` | Record one run-item outcome per candidate and maintain accurate success/failure counters on the parent run. | `P2.4.6` | `app/services/grading_runs.py`, run models | Tests for success/failure item recording, counter updates, and bounded error-detail storage. |
| A.3 | `P2.4.8 - Test - Add deterministic run-ledger persistence tests - Stream A (Dependent)` | Add focused tests covering run creation, transitions, per-item recording, and summary counts. | `P2.4.7` | `tests/test_grading_runs.py` (new) | `pytest tests/test_grading_runs.py -q`. |

### Stream A Acceptance Criteria
- [ ] Run rows track target window, trigger source, runtime snapshot, and terminal status correctly.
- [ ] Run-item rows classify candidate outcomes using the Phase 3 result model.
- [ ] Parent-run counters remain consistent with stored run-item rows.
- [ ] Stream A tests cover both normal and invalid state-transition paths.

## Stream B - Batch Executor and Idempotent Date Windows

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.4.9 - Service - Implement date-window planning with scheduled/manual skip-rerun policy - Stream B (Dependent)` | Build candidate planning for previous-day scheduled runs and bounded manual date windows, including skip/rerun policy. | `P2.4.5` | `app/services/grading_batch.py`, `app/services/grading_extraction.py` (if helper extensions are needed) | Tests for previous-day targeting, bounded date ranges, and rerun/skip behavior. |
| B.2 | `P2.4.10 - Service - Implement batch executor over customer-day candidates with advisory locking - Stream B (Dependent)` | Execute one run across candidates, consume `grade_customer_day()` results, persist run history, and prevent duplicate concurrent runs for the same window. | `P2.4.7`, `P2.4.9` | `app/services/grading_batch.py`, `app/services/grading_pipeline.py` (only if helper return values need extension) | Executor tests for all controlled result paths plus duplicate-run prevention. |
| B.3 | `P2.4.11 - Test - Add batch executor tests for scheduled, rerun, and mixed-failure runs - Stream B (Dependent)` | Add deterministic coverage for completed, completed-with-failures, and aborted run outcomes. | `P2.4.10` | `tests/test_grading_batch.py` (new) | `pytest tests/test_grading_batch.py -q`. |

### Stream B Acceptance Criteria
- [ ] Scheduled runs target the previous GST day deterministically.
- [ ] Manual date windows are validated and bounded by config.
- [ ] Batch execution records candidate results without treating controlled failures as unhandled exceptions.
- [ ] Duplicate concurrent execution for the same target window is blocked or rejected deterministically.
- [ ] Stream B tests cover rerun-safe overwrite behavior and mixed-outcome summaries.

## Stream C - Manual Trigger and Run History API

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.4.12 - Service - Implement manual run trigger/list/detail service wrappers and access checks - Stream C (Dependent)` | Add service-layer entry points that validate manual trigger requests, enforce access policy, and expose run-history reads. | `P2.4.4`, `P2.4.10` | `app/services/grading_runs.py`, `app/services/grading_batch.py`, auth dependency/guard helpers if needed | Service tests for validation, access denial, and history retrieval. |
| C.2 | `P2.4.13 - API - Add protected grading run trigger and history endpoints - Stream C (Dependent)` | Implement manual trigger plus run-history endpoints under `/api/v1/grading/runs`. | `P2.4.12` | `app/api/routes/grading_runs.py` (new), `app/api/router.py`, `app/api/routes/__init__.py` | Route tests for 200/202/401/403/422 plus payload contract verification. |
| C.3 | `P2.4.14 - Test - Add grading run API tests for auth, validation, and history payloads - Stream C (Dependent)` | Cover elevated-access behavior, invalid date-window requests, and run-history responses. | `P2.4.13` | `tests/test_grading_runs_api.py` (new), `tests/conftest.py` (fixture extensions if required) | `pytest tests/test_grading_runs_api.py -q`. |

### Stream C Acceptance Criteria
- [ ] Manual trigger requests validate date-window and rerun flags consistently.
- [ ] Run-history endpoints return stable summary/detail payloads for operators.
- [ ] Protected grading-run routes enforce the finalized elevated-access policy.
- [ ] Stream C tests cover auth failures, validation failures, and populated history responses.

## Stream D - Daily Scheduling, Phase Validation, and Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.4.15 - Infra - Add previous-day scheduler hook and stale-run recovery path - Stream D (Dependent)` | Add the daily scheduling hook that launches the previous-day run and handles stale in-progress run recovery/reporting. | `P2.4.10` | `app/main.py`, `app/services/grading_scheduler.py`, config/constants modules | Targeted scheduler tests or deterministic invocation tests for enabled/disabled and stale-run paths. |
| D.2 | `P2.4.16 - QA - Run compile and targeted pytest verification for batch/run-management scope - Stream D (Dependent)` | Execute compile and focused pytest verification for run ledger, batch executor, scheduler, and API paths. | `P2.4.11`, `P2.4.14`, `P2.4.15` | No mandatory code files; QA notes in task records | `python -m compileall app tests` and targeted grading run pytest suites. |
| D.3 | `P2.4.17 - Docs - Update task/progress docs with Phase 4 execution notes and Phase 5/6 handoff risks - Stream D (Dependent)` | Sync docs after execution/review and capture residual operational risks for metrics/monitoring phases. | `P2.4.16` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-4.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Acceptance Criteria
- [ ] Daily scheduling can launch the previous-day run only when Phase 4 settings are enabled and valid.
- [ ] Stale in-progress runs are surfaced/recovered deterministically rather than left ambiguous.
- [ ] Compile checks pass for modified Python modules.
- [ ] Targeted grading-run test suites pass or any environment blocker is explicitly documented.
- [ ] Docs are synchronized with execution/review outcomes and Phase 5/6 handoff notes.

## Suggested Files by Concern
- Config and constants:
  - `app/core/config.py`
  - `app/core/constants.py`
  - `.env.example`
- Models/migrations:
  - `app/models/grading_runs.py` (new)
  - `app/models/__init__.py`
  - `alembic/versions/*.py`
- Schemas:
  - `app/schemas/grading_runs.py` (new)
  - `app/schemas/__init__.py`
- Services:
  - `app/services/grading_runs.py` (new)
  - `app/services/grading_batch.py` (new)
  - `app/services/grading_scheduler.py` (new)
  - `app/services/grading_pipeline.py` (only if helper signatures need bounded extension)
  - `app/services/__init__.py`
- Routes/dependencies:
  - `app/api/routes/grading_runs.py` (new)
  - `app/api/router.py`
  - `app/api/routes/__init__.py`
  - auth/role dependency helpers under `app/api/deps/` if required
- Tests:
  - `tests/test_grading_runs.py` (new)
  - `tests/test_grading_batch.py` (new)
  - `tests/test_grading_runs_api.py` (new)
  - `tests/conftest.py` (fixture extensions if needed)

## Component Dependency Summary
- Gate 4.0 defines the run contract, schema, config, and scaffolds used by all downstream work.
- Stream A (run ledger persistence) should land before Stream B so batch execution has durable status/result recording.
- Stream B builds on Phase 3 orchestration plus Stream A persistence to execute one full batch run safely.
- Stream C (manual trigger/history API) depends on Stream B because it should expose the real executor and stored run history.
- Stream D scheduler work depends on Stream B and can proceed in parallel with Stream C once executor behavior is stable.
- Phase 5 and Phase 6 should not start implementation until Phase 4 exposes a stable operational run ledger and scheduling policy.

## Parallelization Map

```text
Gate 4.0 (P2.4.1 - P2.4.5 run contract + schema + scaffolds) -------+
                                                                      |
  |- Stream A (run ledger persistence) -----------------------------> |
                                                                      |
  |- Stream B (batch executor + window policy) ---------------------> |  (after A)
                                                                      |
  |- Stream C (manual trigger + run history API) -------------------> |  (after B)
  |- Stream D (scheduler + validation/docs) ------------------------> |  (scheduler after B; QA/docs after C)
                                                                      v
                  Phase 4 Complete (Batch Execution and Run Management)
```

## Definition of Done (Phase 4)
- [ ] Daily grading can be executed for the previous GST day through a stable batch executor.
- [ ] Manual bounded rerun/backfill can be triggered safely through protected internal entry points.
- [ ] Durable run-history tables record both run-level summaries and customer-day outcomes.
- [ ] Controlled Phase 3 failure results are surfaced explicitly in run history without partial-grade ambiguity.
- [ ] Duplicate concurrent execution for the same target window is prevented deterministically.
- [ ] Targeted tests exist for run ledger, batch execution, scheduler behavior, and protected API contracts.
- [ ] No lint/syntax errors exist in modified Python modules.

## Test Scenarios (Phase 4 Validation)

### Happy Path
- Scheduled execution targets the previous GST day, grades all eligible customer-days, and records a `completed` run.
- Manual one-day trigger creates a run, records candidate items, and persists successful grade writes.
- Manual rerun with `rerun_existing = true` overwrites existing grade rows safely and records a new run history entry.
- Run-history list/detail endpoints return stable summaries and counters for recent runs.

### Edge Cases
- Manual trigger rejects inverted or out-of-bounds date windows.
- Duplicate concurrent trigger for the same date window is rejected or skipped deterministically via the locking policy.
- Mixed candidate outcomes (success + parse/provider/empty-transcript failures) produce `completed_with_failures` with accurate counters.
- Invalid live-run provider configuration blocks scheduled/manual execution cleanly.
- App restart/stale-run recovery path does not leave ambiguous forever-running run rows.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- Scheduled automation remains in-process in the current backend unless later deployment constraints require an external orchestrator to call the same batch service/endpoint.
- Daily execution targets the previous GST day only.
- Manual backfill remains bounded by config and is not an unbounded historical regrade tool.
- Run history stores operational metadata and failure summaries, not duplicated transcripts or raw provider outputs.
- Phase 4 may introduce a minimal role guard helper if elevated access is required beyond the Phase 2 authenticated baseline.

### Open Questions
- Should run-history read access include `company_admin`, or be limited to `super_admin` only?
- Is retroactive backfill allowed before the Milestone 2 go-live date, or should Gate 4.0 enforce a lower bound?
- Should manual trigger return immediately after queueing a run, or wait for synchronous completion in the initial implementation path?
- If deployment runs multiple API instances, is the in-process scheduler still acceptable, or should operational automation call the same executor from outside the web process?

## Estimated Duration (Units)
- Gate 4.0 (`P2.4.1` - `P2.4.5`): `2.5`
- Stream A (`P2.4.6` - `P2.4.8`): `1.5`
- Stream B (`P2.4.9` - `P2.4.11`): `1.75`
- Stream C (`P2.4.12` - `P2.4.14`): `1.5`
- Stream D (`P2.4.15` - `P2.4.17`): `1.0`
- Sequential total: `8.25`
- Parallelized total after Gate (A, then B, then C/D overlap): `~6.0 - 6.5`

## Done Condition for Phase 4 Planning
Phase 4 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-4.md`).
- Gate/stream tasks are atomic, dependency-linked, and execution-ready.
- `docs/tasks.md` checklist includes Phase 4 task entries aligned to this plan.
- Kanban task creation remains deferred unless explicitly requested.
