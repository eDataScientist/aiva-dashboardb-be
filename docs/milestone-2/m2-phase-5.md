# Milestone 2 - Phase 5 Plan: AI Quality Metrics API

## Goals
- Deliver a new graded-data API surface for the AI Quality Metrics page without breaking the existing Milestone 1 raw-chat analytics endpoints.
- Expose daily trend data for score-based metrics, outcome-rate metrics, escalation mix, and canonical intent analytics using `conversation_grades`.
- Surface grading freshness from the latest successful run so clients can distinguish "no data" from "data has not been graded yet".
- Keep metrics correctness anchored to persisted grade rows, with `grading_runs` used only for operational freshness metadata.
- Leave Phase 5 in a reviewable state with stable schemas, deterministic tests, and clear handoff boundaries for Phase 6 monitoring work.

## Planning Analysis (Required Order)

### 1) Data Models
- `conversation_grades` is the primary Phase 5 fact table.
  - Grain remains one canonical customer-day grade row per `identity_type` + `conversation_identity` + `grade_date`.
  - Query bucketing should use `grade_date` directly, not `created_at`, because the grade row already represents the GST business day.
- `grading_runs` is a secondary Phase 5 source.
  - It should be read only for freshness metadata such as the latest completed grading window and the last successful run timestamp.
  - Core score/rate/intent aggregates must not depend on run-item internals or candidate counters.
- Phase 5 graded metrics should cover:
  - score averages:
    - `relevancy_score`
    - `accuracy_score`
    - `completeness_score`
    - `clarity_score`
    - `tone_score`
    - `repetition_score`
    - `satisfaction_score`
    - `frustration_score`
  - outcome / rate metrics:
    - `resolution`
    - `loop_detected`
    - `user_relevancy`
    - `escalation_occurred`
    - `escalation_type`
  - intent analytics:
    - canonical `intent_code`
    - canonical `intent_label`
    - taxonomy category metadata derived from the fixed 16-code map
- Phase 5 should not introduce new persisted metric columns unless query-read performance proves an additive index is necessary.
- Highlight computation remains a Phase 6 monitoring concern; Phase 5 should expose raw metric inputs needed by the frontend, not a second highlight engine.

### 2) Migration
- Default path: additive-only or no migration.
- A gate task should validate whether the current schema is read-ready for Phase 5 query patterns:
  - date-window filtering on `conversation_grades.grade_date`
  - grouped intent lookups on `intent_code`
  - escalation mix lookups on `escalation_type`
  - latest-successful-run freshness lookups on `grading_runs`
- If indexes are missing for the expected query patterns, Phase 5 may add only bounded read-path indexes, for example:
  - `conversation_grades(grade_date)`
  - `conversation_grades(grade_date, intent_code)`
  - `conversation_grades(grade_date, escalation_type)`
- No destructive schema changes are allowed.
- No migration should alter the Phase 3 canonical uniqueness or the Phase 4 run-ledger lifecycle contract.

### 3) Dependencies
- Upstream dependencies satisfied:
  - Phase 1 canonical intent taxonomy and conversation-grade contract
  - Phase 2 authentication baseline
  - Phase 3 and 3.5 grading output, persistence, and prompt-pack runtime
  - Phase 4 manual/scheduled execution, run ledger, and scheduler freshness model
- Phase 5 must preserve two separations:
  - metrics correctness from `conversation_grades`
  - operational freshness from `grading_runs`
- Existing `/api/v1/analytics/*` endpoints are Milestone 1 raw-chat analytics.
  - Phase 5 should not silently repurpose them because the data semantics differ.
  - New consumers should use an additive graded-metrics route group instead.
- Phase 6 monitoring should reuse the same canonical grade semantics, metric labels, and intent metadata defined here rather than inventing a second contract.

### 4) Configuration
- Phase 5 should add explicit query-window defaults and bounds for graded metrics:
  - default date window: last 30 graded GST days
  - default end date: previous GST business day
  - max query span: bounded by config/validation to avoid unbounded aggregate scans
- Shared metric registry constants should be centralized so schemas, services, and tests cannot drift on:
  - score metric keys
  - outcome-rate keys
  - escalation breakdown values
  - intent category metadata
- No new provider/runtime settings are required for Phase 5 aggregates themselves.
- Freshness responses should tolerate environments where grading has not run yet and return null freshness metadata instead of failing.

### 5) Endpoints
- Planned additive route group: `/api/v1/grading/metrics/*`
- Planned baseline endpoints:
  - `GET /api/v1/grading/metrics/summary`
    - aggregate scorecards for the selected window
    - escalation mix summary
    - freshness metadata from the latest successful run
  - `GET /api/v1/grading/metrics/score-trends`
    - daily averages for the numeric score metrics
  - `GET /api/v1/grading/metrics/outcome-trends`
    - daily percentages for boolean / enum-derived outcomes
  - `GET /api/v1/grading/metrics/intents/distribution`
    - aggregate canonical intent counts/shares for the selected window
  - `GET /api/v1/grading/metrics/intents/trend`
    - daily zero-filled intent series for all or selected canonical intent codes
- Access baseline for Phase 5:
  - `super_admin`: allowed
  - `company_admin`: allowed
  - `analyst`: allowed
- This keeps parity with the existing authenticated analytics baseline while tenant scoping remains out of scope.

## Dependencies
- Phase dependency: `Milestone 2 Phase 4 complete -> Milestone 2 Phase 5`
- Downstream impact:
  - Phase 6 monitoring should consume the same canonical metric names, intent taxonomy metadata, and freshness semantics.
  - Phase 7 QA should validate both the new graded-metrics surface and the continued stability of the older Milestone 1 raw-chat analytics endpoints.

## Phase 5 Contract Outline (Planning Baseline)

### Route Strategy
- Keep legacy Milestone 1 analytics routes unchanged:
  - `/api/v1/analytics/summary`
  - `/api/v1/analytics/message-volume-trend`
  - `/api/v1/analytics/top-intents`
  - `/api/v1/analytics/peak-hours`
  - `/api/v1/analytics/quality-trend`
  - `/api/v1/analytics/lead-conversion-trend`
- Introduce additive graded-data routes under `/api/v1/grading/metrics/*`.
- This avoids a breaking change where the same endpoint name would switch from chat-derived metrics to grade-derived metrics.

### Date Semantics
- All Phase 5 filters apply to `conversation_grades.grade_date`.
- Default window:
  - `end_date = previous GST day`
  - `start_date = end_date - 29 days`
- Validation rules:
  - reject inverted windows (`start_date > end_date`)
  - reject future dates relative to the previous GST day
  - reject spans wider than the configured max metrics range
- Trend endpoints should return zero-filled daily points across the requested date window so frontend charts do not need to backfill missing dates.

### Summary Semantics
- Summary response should expose:
  - selected date window
  - `total_graded_customer_days`
  - average values for all numeric score metrics
  - rate values for key boolean/enum-derived outcomes
  - escalation breakdown across `Natural`, `Failure`, and `None`
  - freshness metadata:
    - latest successful target end date
    - latest successful run id
    - latest successful run finished timestamp
- If the selected window has no grade rows:
  - count fields return `0`
  - numeric averages / rates return `0.0`
  - freshness fields remain independently populated if successful runs exist

### Trend Semantics
- Score trends should report daily averages for:
  - `relevancy`
  - `accuracy`
  - `completeness`
  - `clarity`
  - `tone`
  - `repetition`
  - `satisfaction`
  - `frustration`
- Outcome trends should report daily percentages for:
  - `resolution_rate_pct`
  - `loop_detected_rate_pct`
  - `non_genuine_rate_pct`
  - `escalation_rate_pct`
  - `escalation_failure_rate_pct`
- Daily denominators should be the number of grade rows for each day.
- Empty days in range should still be returned with zero-valued points.

### Intent Semantics
- Intent distribution should default to all 16 canonical intent codes and always return:
  - `intent_code`
  - `intent_label`
  - `intent_category`
  - `count`
  - `share_pct`
- Intent trend should support:
  - default: all canonical intent codes
  - optional filter: one or more selected `intent_code` values
- Intent trend payloads should be zero-filled per requested code across the whole date range.
- Phase 5 should not expose raw chatbot free-text intent values; only canonical Phase 1/3 intent metadata is valid.

### Freshness Semantics
- Freshness is an operational hint, not the source of metric correctness.
- The "latest successful run" baseline should include both:
  - `completed`
  - `completed_with_failures`
- A fully `failed` run must not replace previously successful freshness metadata.
- Summary freshness should be derived from the latest successful run by `finished_at` / `created_at`, not from latest grade row insertion time alone.

## Gate 5.0 - Graded Metrics Contract and Readiness

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 5.0.1 | `P2.5.1 - Design - Finalize graded metrics contract, freshness semantics, and route access - Gate (Independent)` | Lock the graded metrics route strategy, date-window rules, summary/trend contracts, freshness semantics, and access baseline. | None | `docs/milestone-2/m2-phase-5.md`, `docs/milestone-2/milestone-notes.md` | Review checklist confirms additive route strategy and freshness semantics are explicit. |
| 5.0.2 | `P2.5.2 - DB - Validate grade-read index readiness and add additive indexes if needed - Gate (Dependent)` | Confirm `conversation_grades` and `grading_runs` are query-ready for Phase 5 aggregate reads; add additive indexes only if needed. | `P2.5.1` | `app/models/conversation_grades.py`, `app/models/grading_runs.py`, `alembic/versions/*.py` (conditional) | Migration smoke if revision added; no destructive schema changes. |
| 5.0.3 | `P2.5.3 - Config - Add metrics query defaults and canonical metric registry - Gate (Dependent)` | Add bounded date-window config/constants plus canonical metric and intent-category registries. | `P2.5.1` | `app/core/constants.py`, `app/core/config.py`, `.env.example`, `tests/test_grading_config.py` | Config validation tests for range bounds and constant drift. |
| 5.0.4 | `P2.5.4 - API - Define AI quality metrics schemas and error payloads - Gate (Dependent)` | Add typed filter, summary, trend, intent, and freshness schemas for the new graded metrics surface. | `P2.5.1`, `P2.5.3` | `app/schemas/grading_metrics.py` (new), `app/schemas/__init__.py`, `tests/test_grading_schemas.py` | Schema validation tests and import/OpenAPI smoke checks. |
| 5.0.5 | `P2.5.5 - Service - Scaffold graded metrics query/module boundaries - Gate (Dependent)` | Create dedicated service boundaries for graded aggregates without mutating the Milestone 1 analytics service. | `P2.5.2`, `P2.5.4` | `app/services/grading_metrics.py` (new), `app/services/__init__.py` | Compile/import smoke ensures new module boundaries are discoverable and non-circular. |

### Gate 5.0 Acceptance Criteria
- [ ] Phase 5 uses an additive graded-metrics route group rather than mutating legacy raw-chat analytics semantics.
- [ ] Date-window defaults and bounds are explicit and validated.
- [ ] Freshness semantics are defined independently from metric aggregation correctness.
- [ ] Typed request/response schemas exist for summary, trends, and intent analytics.
- [ ] Service boundaries are established for graded aggregate queries.

### P2.5.1 Decision Record - Graded Metrics Contract, Freshness, and Access

#### Decision Summary
- Phase 5 introduces additive graded-data endpoints under `/api/v1/grading/metrics/*`.
- Existing `/api/v1/analytics/*` endpoints remain Milestone 1 raw-chat analytics and are not repurposed in Phase 5.
- Grade aggregates read `conversation_grades`; freshness reads `grading_runs`; run-item rows remain out of scope for client-facing metrics APIs.
- Access baseline for Phase 5 is any authenticated active role, matching the current analytics access model.

#### Access Matrix

| Endpoint / Action | `super_admin` | `company_admin` | `analyst` |
|---|---|---|---|
| `GET /api/v1/grading/metrics/summary` | allowed | allowed | allowed |
| `GET /api/v1/grading/metrics/score-trends` | allowed | allowed | allowed |
| `GET /api/v1/grading/metrics/outcome-trends` | allowed | allowed | allowed |
| `GET /api/v1/grading/metrics/intents/distribution` | allowed | allowed | allowed |
| `GET /api/v1/grading/metrics/intents/trend` | allowed | allowed | allowed |

#### Why Phase 5 Is Not `super_admin`-Only
- These endpoints expose business-facing aggregate metrics rather than global operator run history.
- The project already allows authenticated analytics access for any active role.
- Phase 5 keeps that baseline stable until tenant/company scoping is added in a later milestone.

#### Freshness Contract
- "Successful freshness" includes:
  - `completed`
  - `completed_with_failures`
- Freshness fields should identify the latest successful run without requiring clients to inspect run-history endpoints.
- Metric aggregates do not read run-item counters and do not derive counts from `grading_runs`.

#### Route and Payload Strategy
- Summary returns the selected window, aggregate scorecards, escalation mix, and freshness.
- Score/outcome trends return zero-filled daily series for the requested date range.
- Intent distribution/trend returns canonical intent metadata, not legacy free-text source intent values.

## Stream A - Window Summary and Freshness

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.5.6 - Service - Implement window summary aggregates from conversation_grades - Stream A (Dependent)` | Build selected-window score/rate aggregates directly from `conversation_grades`. | `P2.5.5` | `app/services/grading_metrics.py` | Service tests for populated and empty windows. |
| A.2 | `P2.5.7 - Service - Implement latest-successful-run freshness and escalation mix helpers - Stream A (Dependent)` | Add freshness lookup from `grading_runs` plus escalation breakdown helpers for the summary response. | `P2.5.6` | `app/services/grading_metrics.py`, `app/models/grading_runs.py` (only if read helpers are needed) | Tests for `completed` vs `completed_with_failures` freshness and no-run cases. |
| A.3 | `P2.5.8 - Test - Add summary and freshness service tests - Stream A (Dependent)` | Add deterministic coverage for summary math, escalation mix, and freshness fallback behavior. | `P2.5.7` | `tests/test_grading_metrics.py` (new) | `pytest tests/test_grading_metrics.py -q`. |

### Stream A Acceptance Criteria
- [ ] Summary aggregates are computed from `conversation_grades` only.
- [ ] Freshness is populated from the latest successful run without requiring run-item reads.
- [ ] Empty windows return stable zero-valued aggregate payloads.
- [ ] Stream A tests cover both populated and stale/no-run scenarios.

## Stream B - Score and Outcome Trends

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.5.9 - Service - Implement daily numeric score trend aggregations - Stream B (Dependent)` | Return daily zero-filled averages for the numeric quality metrics. | `P2.5.5` | `app/services/grading_metrics.py` | Trend tests for sparse and populated date ranges. |
| B.2 | `P2.5.10 - Service - Implement daily outcome-rate trend aggregations - Stream B (Dependent)` | Return daily zero-filled percentages for resolution, loop, non-genuine, escalation, and escalation-failure outcomes. | `P2.5.9` | `app/services/grading_metrics.py` | Tests for boolean/enum denominator handling and zero-fill behavior. |
| B.3 | `P2.5.11 - Test - Add deterministic graded trend tests - Stream B (Dependent)` | Add focused coverage for score averages, rate percentages, and zero-filled day buckets. | `P2.5.10` | `tests/test_grading_metrics.py` | `pytest tests/test_grading_metrics.py -q`. |

### Stream B Acceptance Criteria
- [ ] Numeric score trends return daily averages per metric for every day in range.
- [ ] Outcome trends return stable daily percentages with correct denominators.
- [ ] Empty days are zero-filled across all trend responses.
- [ ] Stream B tests cover sparse, empty, and mixed-outcome windows.

## Stream C - Intent Distribution and Trend

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.5.12 - Service - Implement aggregate intent distribution with taxonomy metadata - Stream C (Dependent)` | Build canonical intent count/share payloads with category metadata for the selected window. | `P2.5.5` | `app/services/grading_metrics.py`, `app/core/constants.py` | Tests verify all 16 canonical intents and zero-count rows are handled consistently. |
| C.2 | `P2.5.13 - Service - Implement daily intent trend aggregation with optional intent filters - Stream C (Dependent)` | Return zero-filled daily intent series for all or selected canonical intent codes. | `P2.5.12` | `app/services/grading_metrics.py` | Tests for filtered and unfiltered intent trend queries. |
| C.3 | `P2.5.14 - Test - Add deterministic intent analytics tests - Stream C (Dependent)` | Add coverage for canonical-code filtering, category metadata, and zero-filled intent trends. | `P2.5.13` | `tests/test_grading_metrics.py` | `pytest tests/test_grading_metrics.py -q`. |

### Stream C Acceptance Criteria
- [ ] Intent distribution exposes canonical intent codes, labels, and category metadata only.
- [ ] Intent trend supports all-intent and selected-intent queries with stable zero-filled output.
- [ ] Phase 5 never falls back to legacy raw chatbot intent strings.
- [ ] Stream C tests cover absent-intent and multi-intent-date windows.

## Stream D - API, Validation, and Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.5.15 - API - Add protected graded metrics endpoints - Stream D (Dependent)` | Implement the `/api/v1/grading/metrics/*` route group and register it in the API router. | `P2.5.8`, `P2.5.11`, `P2.5.14` | `app/api/routes/grading_metrics.py` (new), `app/api/routes/__init__.py`, `app/api/router.py` | Route smoke checks and import/OpenAPI verification. |
| D.2 | `P2.5.16 - Test - Add graded metrics API tests for auth, validation, and payload contracts - Stream D (Dependent)` | Cover auth behavior, invalid date windows, empty payloads, and populated response contracts. | `P2.5.15` | `tests/test_grading_metrics_api.py` (new), `tests/conftest.py` (fixture extensions if needed) | `pytest tests/test_grading_metrics_api.py -q`. |
| D.3 | `P2.5.17 - QA - Run compile and targeted pytest verification for metrics API scope - Stream D (Dependent)` | Execute compile and targeted pytest checks for schemas, services, and routes in Phase 5 scope. | `P2.5.16` | No mandatory code files; QA notes in task records | `python -m compileall app tests` and targeted grading-metrics pytest suites. |
| D.4 | `P2.5.18 - Docs - Update task/progress docs with Phase 5 execution notes and Phase 6/7 handoff risks - Stream D (Dependent)` | Sync docs after execution/review and capture Phase 6 monitoring + Phase 7 QA handoff risks. | `P2.5.17` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-5.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Acceptance Criteria
- [x] New graded metrics routes are protected and registered cleanly.
- [x] Route tests cover auth, validation, empty-state, and populated-state contracts.
- [x] Compile and targeted pytest verification are executed or blockers are explicitly documented.
- [x] Docs remain synchronized with execution and review outcomes.

### Stream D Execution Notes (`2026-03-13`)
- `app/api/routes/grading_metrics.py` created with five endpoints under `/api/v1/grading/metrics/*`.
- Date-window and intent-code validation errors are caught inside async sub-dependencies (`_parse_window_query`, `_parse_intent_trend_query`) and returned as `GradingMetricsErrorResponse` with stable error codes.
- `app/api/routes/__init__.py` and `app/api/router.py` updated to register `grading_metrics_router`.
- `app/services/__init__.py` updated to export `get_grading_metrics_summary`.
- `tests/test_grading_metrics_api.py` created with 19 tests covering auth, role access, validation rejection, empty-state zeros, and populated payload shapes.
- `python -m compileall` passed; unrestricted `pytest tests/test_grading_metrics_api.py -q` passed `19 passed`.

## Suggested Files by Concern
- Config and constants:
  - `app/core/constants.py`
  - `app/core/config.py`
  - `.env.example`
- Models / migrations:
  - `app/models/conversation_grades.py`
  - `app/models/grading_runs.py`
  - `alembic/versions/*.py` (conditional)
- Schemas:
  - `app/schemas/grading_metrics.py` (new)
  - `app/schemas/__init__.py`
- Services:
  - `app/services/grading_metrics.py` (new)
  - `app/services/__init__.py`
- Routes:
  - `app/api/routes/grading_metrics.py` (new)
  - `app/api/routes/__init__.py`
  - `app/api/router.py`
- Tests:
  - `tests/test_grading_metrics.py` (new)
  - `tests/test_grading_metrics_api.py` (new)
  - `tests/test_grading_config.py`
  - `tests/test_grading_schemas.py`
  - `tests/conftest.py` (if fixture extensions are needed)

## Component Dependency Summary
- Gate 5.0 defines the graded metrics contract, any conditional read indexes, config bounds, schemas, and service boundaries.
- Stream A, Stream B, and Stream C can run in parallel after Gate 5.0 because they operate on separate aggregate concerns over the same underlying grade table.
- Stream D depends on A/B/C so the route layer exposes real summary, trend, and intent analytics rather than placeholders.
- Phase 6 monitoring should reuse the same metric keys and intent metadata from Phase 5 rather than rebuilding them in monitoring-specific code.

## Parallelization Map

```text
Gate 5.0 (P2.5.1 - P2.5.5 graded metrics contract + readiness) ----+
                                                                     |
  |- Stream A (summary + freshness) -------------------------------> |
  |- Stream B (score + outcome trends) ----------------------------> |  (parallel after Gate)
  |- Stream C (intent distribution + trend) -----------------------> |
                                                                     |
  |- Stream D (API + tests + QA + docs) --------------------------> |  (after A/B/C)
                                                                     v
                 Phase 5 Complete (AI Quality Metrics API)
```

## Definition of Done (Phase 5)
- [x] New graded metrics endpoints exist under `/api/v1/grading/metrics/*`.
- [x] Existing Milestone 1 raw-chat analytics endpoints remain stable and unchanged in meaning.
- [x] Summary, score trends, outcome trends, and intent analytics are driven by `conversation_grades`.
- [x] Freshness metadata is surfaced from `grading_runs` without becoming the source of aggregate truth.
- [x] Date-window defaults, bounds, and zero-fill behavior are deterministic and documented.
- [x] Targeted tests exist for service and route contracts in Phase 5 scope.
- [x] No lint/syntax errors exist in modified Python modules.

## Test Scenarios (Phase 5 Validation)

### Happy Path
- Summary endpoint returns populated averages, rates, escalation mix, and freshness for a date window containing graded rows.
- Score trend endpoint returns daily averages for all score metrics across a populated date range.
- Outcome trend endpoint returns daily percentages for resolution, loop, escalation, and non-genuine signals.
- Intent distribution returns canonical counts/shares with category metadata.
- Intent trend returns daily series for all intents or a selected subset.

### Edge Cases
- Empty date window returns stable zero-valued payloads rather than null-heavy or shape-shifting responses.
- Invalid or out-of-bounds date ranges fail with a stable validation error envelope.
- Latest run is `failed` but a prior successful run exists; freshness should still point to the last successful run.
- Intent filter includes one or more valid codes with no matching rows; output remains zero-filled and schema-stable.
- Existing `/api/v1/analytics/*` routes continue to return raw-chat analytics semantics after Phase 5 code lands.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- The frontend AI Quality Metrics page can consume an additive route group rather than requiring a breaking rewrite of legacy `/api/v1/analytics/*` contracts.
- Grade freshness should reflect the latest successful completed run even when that run includes some controlled candidate failures.
- Tenant-scoped metrics remain out of scope for Milestone 2; the existing authenticated-any-role baseline remains acceptable for now.
- Intent category grouping can be derived from the canonical code map in application constants without extra database tables.

### Open Questions
- None currently. Gate 5.0 decisions were locked during planning on `2026-03-13`:
  - Phase 5 adds `/api/v1/grading/metrics/*` instead of repurposing legacy analytics routes
  - grade aggregates come from `conversation_grades`
  - freshness comes from the latest successful `grading_runs` row
  - access remains any authenticated active role

## Estimated Duration (Units)
- Gate 5.0 (`P2.5.1` - `P2.5.5`): `2.25`
- Stream A (`P2.5.6` - `P2.5.8`): `1.25`
- Stream B (`P2.5.9` - `P2.5.11`): `1.5`
- Stream C (`P2.5.12` - `P2.5.14`): `1.25`
- Stream D (`P2.5.15` - `P2.5.18`): `1.25`
- Sequential total: `7.5`
- Parallelized total after Gate (A/B/C concurrent, then D): `~5.0 - 5.5`

## Done Condition for Phase 5 Planning
Phase 5 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-5.md`).
- `docs/tasks.md` includes Phase 5 task entries aligned to this plan.
- `docs/project-progress.md` records Phase 5 as the current planned phase and notes that kanban creation remains deferred.
- Kanban task creation remains deferred unless explicitly requested.
