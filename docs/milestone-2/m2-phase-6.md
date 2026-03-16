# Milestone 2 - Phase 6 Plan: Conversations Monitoring API Overhaul

## Goals
- Deliver a dedicated analyst monitoring API centered on canonical customer-day grade rows instead of the legacy cross-range conversation list.
- Surface server-side filtering, sorting, paging, and highlight badges for problematic graded conversations without mutating raw chat data.
- Add a customer-day detail response that combines the full grade panel, same-day transcript, and recent grade history timeline for the same canonical identity.
- Preserve a separate full-conversation view across time by linking Phase 6 monitoring payloads to the existing `/api/v1/conversations/{conversation_key}/messages` surface.
- Leave Phase 6 in a reviewable state with deterministic service and API tests plus a clean handoff into Phase 7 QA/hardening.

## Planning Analysis (Required Order)

### 1) Data Models
- `conversation_grades` is the primary Phase 6 fact table.
  - Grain remains one canonical customer-day row per `identity_type` + `conversation_identity` + `grade_date`.
  - Monitoring list and detail should be anchored to persisted grade rows rather than rebuilding customer-day candidates from raw chats on every request.
- Raw chat reads remain necessary for analyst-facing transcript context.
  - Same-day transcript/detail should derive from `ChatMessage` by joining on canonical identity plus GST `grade_date`.
  - Existing helpers in `app/services/grading_extraction.py` (`canonical_identity_*`, `gst_grade_date_expr()`, `build_customer_day_messages_stmt()`) should be reused so Phase 6 does not fork identity/date logic from Phase 3.
- `monitoring_highlight_config` is the read-time highlight-rules source.
  - Highlights remain computed on read.
  - No highlight flags are persisted on `conversation_grades`.
  - Historical rows use the current-rules view because config versioning is still out of scope.
- Phase 6 monitoring payloads should expose canonical grade-derived metadata already established upstream:
  - intent: `intent_code`, `intent_label`, `intent_category`
  - outcomes: `resolution`, `escalation_type`
  - numeric triage scores: `frustration_score`, `accuracy_score`
  - highlight badges: canonical `highlight_code` + label pairs
- Detail payloads should include:
  - one customer-day grade panel with all scores, booleans, enums, and reasoning
  - same-day transcript/messages
  - recent grade-history timeline for the same canonical identity
  - `conversation_key` so clients can pivot to the existing full-conversation route across time

### 2) Migration
- Default path: additive-only or no migration.
- Gate validation should confirm whether `conversation_grades` is read-ready for Phase 6 list/detail patterns:
  - date-window filtering on `grade_date`
  - optional filters on `resolution`, `escalation_type`, and `intent_code`
  - server-side sorts on `frustration_score` and `accuracy_score`
  - point lookups by canonical identity + `grade_date`
- If current indexes are insufficient, Phase 6 may add bounded read-path indexes such as:
  - `conversation_grades(grade_date, resolution)`
  - `conversation_grades(grade_date, frustration_score)`
  - `conversation_grades(grade_date, accuracy_score)`
- Phase 6 should not modify raw chat table structure.
  - No new columns, foreign keys, or linkage fields on `"Arabia Insurance Chats"`.
  - Transcript/message association remains derived at read time.
- `monitoring_highlight_config` already exists and should not require schema changes unless a concrete gap is discovered during Gate 6.0 review.

### 3) Dependencies
- Upstream dependencies satisfied:
  - Phase 1: canonical identity contract, highlight config table, highlight code registry, intent taxonomy constants
  - Phase 2: authenticated-any-role baseline on analytics/conversations surfaces
  - Phase 3 and 3.5: persisted grade rows, canonical intent storage, transcript assembly helpers, prompt-pack grading runtime
  - Phase 4: latest-successful run ledger and scheduler freshness model
  - Phase 5: canonical intent metadata and latest-successful freshness semantics already exposed to clients
- Phase 6 should explicitly reuse, not re-declare:
  - `INTENT_CODE_TO_LABEL` / `INTENT_CODE_TO_CATEGORY`
  - highlight code-to-label constants
  - latest-successful freshness semantics from Phase 5 (`completed` and `completed_with_failures`)
- Existing `/api/v1/conversations/*` behavior should remain stable for legacy/full-history consumers.
  - Phase 6 adds a new customer-day monitoring surface instead of repurposing the Milestone 1 conversations list.

### 4) Configuration
- Phase 6 should add bounded monitoring query configuration for:
  - default monitoring date window
  - maximum monitoring date window
  - default page size
  - maximum page size
  - default recent-history timeline length in detail responses
- Planning baseline:
  - default monitoring window: previous GST day only
  - maximum monitoring window: 31 GST days
  - default page size: 50
  - maximum page size: 200
  - default recent-history limit: 30 prior grade rows
- Highlight evaluation should keep the DB-backed config table authoritative.
  - If the active config row is missing or unreadable, service logic should fall back to the seeded Phase 1 defaults and emit an operational warning log instead of failing the analyst response.
- Sort/filter enums should be centralized to keep schemas, services, and tests aligned.

### 5) Endpoints
- Planned additive route group: `/api/v1/monitoring/conversations`
- Planned Phase 6 endpoints:
  - `GET /api/v1/monitoring/conversations`
    - customer-day monitoring list
    - server-side filter/sort/pagination
    - highlight badges and grading freshness metadata
  - `GET /api/v1/monitoring/conversations/{grade_id}`
    - customer-day detail by grade row id
    - same-day transcript
    - full grade panel
    - recent grade-history timeline
    - `conversation_key` for the existing full-conversation route
- Preserved separate endpoint surface:
  - existing `GET /api/v1/conversations/{conversation_key}/messages` remains the cross-day full-conversation view
- Access baseline for Phase 6:
  - `super_admin`: allowed
  - `company_admin`: allowed
  - `analyst`: allowed

## Dependencies
- Phase dependency: `Milestone 2 Phase 5 complete -> Milestone 2 Phase 6`
- Downstream impact:
  - Phase 7 QA should validate the new monitoring surface alongside Phase 5 metrics and the preserved legacy/full-conversation routes.
  - Monitoring should consume the same canonical metric keys, intent metadata, and freshness semantics already stabilized in Phase 5.

## Phase 6 Contract Outline (Planning Baseline)

### Route Strategy
- Add customer-day monitoring routes under `/api/v1/monitoring/conversations`.
- Keep legacy/full-history routes under `/api/v1/conversations/*` unchanged in meaning.
- Monitoring list/detail responses should include `conversation_key` so clients can pivot to the existing full-conversation endpoint without a second identity-encoding scheme.

### Monitoring List Semantics
- List rows are one-to-one with `conversation_grades` rows in the selected window.
- Baseline filters:
  - `start_date`
  - `end_date`
  - `resolution`
  - `escalation_types[]`
  - `frustration_min`
  - `accuracy_max`
  - `intent_codes[]`
  - `limit`
  - `offset`
- Baseline sorting:
  - supported explicit sort fields: `frustration_score`, `accuracy_score`
  - supported directions: `asc`, `desc`
  - default ordering when no explicit sort is requested: `grade_date DESC`, then most recent transcript activity DESC, then `grade_id DESC`
- List payload should include:
  - `grade_id`
  - `grade_date`
  - `conversation_key`
  - best available contact name
  - latest message preview for the customer-day
  - latest message timestamp for the customer-day
  - daily message count
  - `intent_code`, `intent_label`, `intent_category`
  - `resolution`
  - `escalation_type`
  - `frustration_score`
  - `accuracy_score`
  - `highlights[]`
- Empty windows return:
  - `items=[]`
  - `total=0`
  - stable paging metadata
  - freshness metadata populated independently when successful runs exist

### Highlight Semantics
- Canonical highlight codes remain:
  - `frustration_high`
  - `escalation_failure`
  - `loop_detected`
  - `accuracy_low`
  - `unresolved_low_satisfaction`
  - `user_irrelevancy`
- Trigger evaluation uses the current active `monitoring_highlight_config` row.
- Historical highlight behavior in Phase 6 is explicitly "current rules view":
  - changing the active config changes how both recent and historical rows are highlighted in future reads
  - config-at-time versioning remains out of scope

### Detail Semantics
- Detail lookups use `conversation_grades.id` as the stable path key.
- Detail payload should include:
  - grade summary metadata (`grade_id`, `grade_date`, `conversation_key`, contact name)
  - canonical intent metadata
  - triggered highlights
  - grouped grade panel fields:
    - AI Performance
    - Conversation Health
    - User Signals
    - Escalation
    - Intent
  - same-day transcript messages sorted ascending by `created_at`
  - recent grade-history timeline for the same canonical identity, ordered newest-first and bounded by config
- Not-found behavior should use a stable error envelope rather than generic FastAPI payload drift.

### Full Conversation View Strategy
- Phase 6 does not replace the existing cross-time conversation endpoint.
- The monitoring detail response carries `conversation_key` so clients can call `/api/v1/conversations/{conversation_key}/messages` for the preserved full-history view.
- Any Phase 6 route-layer work touching the legacy conversations surface should be additive-only and should not alter its current payload semantics.

### Freshness Semantics
- Monitoring list responses should surface the same latest-successful freshness metadata used in Phase 5 so analysts can distinguish:
  - no rows because nothing matched the filters
  - no rows because grading has not succeeded for the latest expected window yet
- Freshness remains derived from `grading_runs`, not from list/detail transcript timestamps.

## Gate 6.0 - Monitoring Contract and Readiness

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 6.0.1 | `P2.6.1 - Design - Finalize monitoring route strategy, highlight semantics, and access matrix - Gate (Independent)` | Lock additive route strategy, customer-day list/detail contract, current-rules highlight semantics, full-conversation linkage, and access baseline. | None | `docs/milestone-2/m2-phase-6.md`, `docs/milestone-2/milestone-notes.md` | Review checklist confirms route/access/highlight behavior is explicit and stable. |
| 6.0.2 | `P2.6.2 - DB - Validate monitoring-read index readiness and add additive indexes if needed - Gate (Dependent)` | Confirm `conversation_grades` and existing highlight config schema are query-ready for Phase 6 filters/sorts/detail lookups; add bounded read indexes only if needed. | `P2.6.1` | `app/models/conversation_grades.py`, `alembic/versions/*.py` (conditional) | Migration smoke if a revision is added; no raw-chat schema changes. |
| 6.0.3 | `P2.6.3 - Config - Add monitoring query defaults, bounds, and history-limit settings - Gate (Dependent)` | Add and validate monitoring window/page/history settings plus centralized sort/filter constants. | `P2.6.1` | `app/core/constants.py`, `app/core/config.py`, `.env.example`, `tests/test_grading_config.py` | Config validation tests for default/max windows, page size, and history bounds. |
| 6.0.4 | `P2.6.4 - API - Define monitoring list/detail schemas and error payloads - Gate (Dependent)` | Add typed query, list, detail, history, highlight, and error schemas for the new monitoring surface. | `P2.6.1`, `P2.6.3` | `app/schemas/grading_monitoring.py` (new), `app/schemas/__init__.py`, `tests/test_grading_schemas.py` | Schema validation tests and import/OpenAPI smoke checks. |
| 6.0.5 | `P2.6.5 - Service - Scaffold monitoring query and highlight module boundaries - Gate (Dependent)` | Create dedicated service boundaries for highlight evaluation and monitoring list/detail queries without mutating Milestone 1 conversation services. | `P2.6.2`, `P2.6.4` | `app/services/grading_monitoring.py` (new), `app/services/monitoring_highlights.py` (new), `app/services/__init__.py` | Compile/import smoke confirms service boundaries are discoverable and non-circular. |

### P2.6.1 Decision Record - Monitoring Route Strategy, Highlight Semantics, and Access

#### Decision Summary
- Phase 6 introduces additive analyst monitoring endpoints under `/api/v1/monitoring/conversations`.
- Existing `/api/v1/conversations/{conversation_key}/messages` remains the separate full-conversation view across time.
- Monitoring responses are grade-row-first:
  - list/detail are driven by `conversation_grades`
  - raw chats are joined/read only for transcript context and daily preview metadata
  - latest-successful freshness comes from `grading_runs`
- Highlights are computed from the current active `monitoring_highlight_config` row at read time.
- Phase 6 access stays aligned with current authenticated analytics/metrics behavior: any active role may read monitoring data.

#### Access Matrix

| Endpoint / Action | `super_admin` | `company_admin` | `analyst` |
|---|---|---|---|
| `GET /api/v1/monitoring/conversations` | allowed | allowed | allowed |
| `GET /api/v1/monitoring/conversations/{grade_id}` | allowed | allowed | allowed |
| Existing `GET /api/v1/conversations/{conversation_key}/messages` | allowed | allowed | allowed |

#### Current-Rules Highlight Policy
- The active config row determines highlight evaluation for all reads.
- If the active config row is missing, service logic falls back to the seeded Phase 1 defaults and logs an operational warning.
- Historical config versioning is explicitly deferred beyond Phase 6.

#### List/Detail Contract Decisions
- Monitoring list is paginated and server-side filtered/sorted.
- Explicit sort controls are limited to `frustration_score` and `accuracy_score`; all other ordering uses deterministic fallback ordering.
- Detail path key is `grade_id` (`conversation_grades.id`) to avoid exposing identity/date tuples in URLs.
- Detail includes `conversation_key` so clients can pivot to the existing full-conversation endpoint without a second detail-specific route.

### Gate 6.0 Acceptance Criteria
- [ ] Phase 6 uses an additive monitoring route group rather than mutating legacy conversation-list semantics.
- [ ] Highlight current-rules semantics, fallback behavior, and access baseline are explicit.
- [ ] Monitoring query defaults, paging bounds, and history limits are validated at startup/config load.
- [ ] Typed schemas exist for monitoring list/detail responses and validation error envelopes.
- [ ] Dedicated monitoring/highlight service boundaries are established.

## Stream A - Highlight Evaluation and Config Fallback

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.6.6 - Service - Implement active highlight-config loader with seeded-default fallback - Stream A (Dependent)` | Load the active highlight config row and fall back to the seeded Phase 1 defaults when the row is missing/unavailable. | `P2.6.5` | `app/services/monitoring_highlights.py`, `app/models/monitoring_highlight_config.py` (only if read helpers are needed) | Service tests for active-config, missing-config, and fallback behavior. |
| A.2 | `P2.6.7 - Service - Implement read-time highlight evaluation and badge mapping for grade rows - Stream A (Dependent)` | Evaluate canonical highlight codes/labels from one grade row using the active config contract. | `P2.6.6` | `app/services/monitoring_highlights.py`, `app/core/constants.py` | Deterministic tests for each trigger and multi-trigger combinations. |
| A.3 | `P2.6.8 - Test - Add deterministic highlight config and trigger tests - Stream A (Dependent)` | Add focused coverage for highlight rule evaluation, fallback defaults, and canonical badge ordering. | `P2.6.7` | `tests/test_monitoring_highlights.py` (new) | `pytest tests/test_monitoring_highlights.py -q`. |

### Stream A Acceptance Criteria
- [ ] Active highlight config loading is deterministic and resilient to a missing row.
- [ ] Highlight evaluation returns only canonical codes/labels from the shared registry.
- [ ] Multiple trigger conditions can be surfaced together in stable order.
- [ ] Stream A tests cover all configured trigger paths plus fallback behavior.

## Stream B - Customer-Day Monitoring List

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.6.9 - Service - Implement customer-day monitoring list query with filters, pagination, and deterministic ordering - Stream B (Dependent)` | Query canonical grade rows for the selected window with server-side filters, page bounds, and deterministic default ordering. | `P2.6.5` | `app/services/grading_monitoring.py`, `app/models/conversation_grades.py` (only if helper updates are needed) | Service tests for empty/populated windows, paging, and every filter combination. |
| B.2 | `P2.6.10 - Service - Enrich monitoring list items with highlight badges, intent metadata, previews, and freshness - Stream B (Dependent)` | Add highlight badges, same-day preview metadata, canonical intent metadata, and latest-successful freshness to the list response. | `P2.6.7`, `P2.6.9` | `app/services/grading_monitoring.py`, `app/services/monitoring_highlights.py`, `app/services/grading_metrics.py` (reuse only if helpful) | Tests for highlight enrichment, preview selection, and freshness behavior when the window is empty. |
| B.3 | `P2.6.11 - Test - Add deterministic monitoring list service tests - Stream B (Dependent)` | Add focused coverage for filter semantics, sort semantics, preview selection, and empty-state list behavior. | `P2.6.10` | `tests/test_grading_monitoring.py` (new) | `pytest tests/test_grading_monitoring.py -q -k "list"`. |

### Stream B Acceptance Criteria
- [ ] Monitoring list is driven by canonical customer-day grade rows rather than the legacy conversation list query.
- [ ] Filters, paging, and explicit sort controls are stable and server-side enforced.
- [ ] List items include highlight badges, canonical intent metadata, and same-day preview fields.
- [ ] Empty windows remain schema-stable and still expose freshness metadata when available.

## Stream C - Customer-Day Detail, Timeline, and Full-Conversation Linkage

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.6.12 - Service - Implement customer-day detail query with same-day transcript and full grade panel - Stream C (Dependent)` | Load one grade row plus its same-day transcript/messages and grouped grade fields for analyst inspection. | `P2.6.5`, `P2.6.7` | `app/services/grading_monitoring.py`, `app/services/grading_extraction.py` (reuse helpers only as needed) | Service tests for populated detail, transcript ordering, and not-found behavior. |
| C.2 | `P2.6.13 - Service - Add grade-history timeline and full-conversation linkage to monitoring detail - Stream C (Dependent)` | Add bounded recent history for the same canonical identity and expose `conversation_key` for the preserved full-conversation route. | `P2.6.12` | `app/services/grading_monitoring.py`, `app/services/conversations.py` (reuse key encoding helpers only as needed) | Tests for history ordering, limit enforcement, and stable linkage metadata. |
| C.3 | `P2.6.14 - Test - Add deterministic monitoring detail service tests - Stream C (Dependent)` | Cover detail not-found, grouped grade payload shape, same-day transcript contents, and recent-history timeline behavior. | `P2.6.13` | `tests/test_grading_monitoring.py` (new) | `pytest tests/test_grading_monitoring.py -q -k "detail"`. |

### Stream C Acceptance Criteria
- [ ] Detail payload exposes the same-day transcript and the full grouped grade panel for one customer-day.
- [ ] Recent grade-history timeline uses canonical identity + grade-date semantics and is bounded deterministically.
- [ ] Detail includes `conversation_key` so clients can pivot to the preserved full-conversation endpoint.
- [ ] Stream C tests cover populated, empty-history, and not-found paths.

## Stream D - API, Validation, and Phase 7 Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.6.15 - API - Add protected monitoring list and detail endpoints - Stream D (Dependent)` | Implement `/api/v1/monitoring/conversations` list/detail routes and register the new router cleanly. | `P2.6.8`, `P2.6.11`, `P2.6.14` | `app/api/routes/grading_monitoring.py` (new), `app/api/routes/__init__.py`, `app/api/router.py` | Route import/OpenAPI smoke checks and direct handler validation. |
| D.2 | `P2.6.16 - Test - Add monitoring API tests for auth, filters, sort, detail, and error contracts - Stream D (Dependent)` | Cover auth behavior, invalid windows/filters/sorts, empty states, populated list/detail payloads, and stable not-found errors. | `P2.6.15` | `tests/test_grading_monitoring_api.py` (new), `tests/conftest.py` (fixture extensions if needed) | `pytest tests/test_grading_monitoring_api.py -q`. |
| D.3 | `P2.6.17 - QA - Run compile and targeted pytest verification for monitoring scope - Stream D (Dependent)` | Execute compile and focused pytest verification for highlight, monitoring service, route, and preserved-conversation-link contracts. | `P2.6.16` | No mandatory code files; QA notes in task records | `python -m compileall app tests` and targeted monitoring pytest suites. |
| D.4 | `P2.6.18 - Docs - Update task/progress docs with Phase 6 execution notes and Phase 7 handoff risks - Stream D (Dependent)` | Sync docs after execution/review and capture any remaining monitoring/runtime risks for the final QA phase. | `P2.6.17` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-6.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Execution Snapshot (`2026-03-17`)
- `P2.6.15` (`EDA-165`) added `app/api/routes/grading_monitoring.py`, registered the new router through `app/api/routes/__init__.py` and `app/api/router.py`, and exposed stable monitoring validation/not-found envelopes without mutating legacy conversation-route semantics.
- `P2.6.16` (`EDA-166`) added `tests/test_grading_monitoring_api.py` coverage for auth, invalid date-window/filter/sort envelopes, empty-state freshness, populated list/detail payloads, and stable `grade_not_found` responses.
- `P2.6.17` (`EDA-167`) captured verification evidence:
  - `python -m compileall app tests` passed
  - `pytest tests/test_monitoring_highlights.py tests/test_grading_monitoring.py tests/test_grading_monitoring_detail.py tests/test_grading_monitoring_api.py -q` passed (`31 passed`)
  - only third-party Paramiko deprecation warnings were emitted by the test environment
- `P2.6.18` (`EDA-168`) synchronized `docs/tasks.md`, `docs/project-progress.md`, and this phase plan with the Stream D execution state and Phase 7 handoff note.

### Stream D Review-Fix Snapshot (`2026-03-17`)
- `P2.6.15` (`EDA-165`) extended `app/main.py` so monitoring `RequestValidationError` / Pydantic validation failures are classified into the monitoring error envelope as well:
  - malformed date and numeric query parsing now return monitoring `detail` objects instead of raw FastAPI error arrays
  - malformed `grade_id` path parsing now returns monitoring `grade_not_found` code in the normalized envelope
- `P2.6.16` (`EDA-166`) expanded `tests/test_grading_monitoring_api.py` with malformed `start_date`, malformed `frustration_min`, and malformed `grade_id` coverage to lock the end-to-end validation contract.
- `P2.6.17` (`EDA-167`) refreshed verification evidence:
  - `python -m compileall app/main.py app/api/routes/grading_monitoring.py tests/test_grading_monitoring_api.py` passed
  - `pytest tests/test_grading_monitoring_api.py -q` passed (`12 passed`)
  - `pytest tests/test_monitoring_highlights.py tests/test_grading_monitoring.py tests/test_grading_monitoring_detail.py tests/test_grading_monitoring_api.py -q` passed (`34 passed`)
  - only third-party Paramiko deprecation warnings were emitted by the test environment
- `P2.6.18` (`EDA-168`) updated the Stream D execution notes so validation-envelope claims only apply after the malformed-input normalization fix landed.

### Stream D Review Completion (`2026-03-17`)
- `P2.6.15` (`EDA-165`) approved after rereview confirmed the monitoring routes preserve legacy conversation semantics while normalizing malformed monitoring query/path inputs into the documented envelope.
- `P2.6.16` (`EDA-166`) approved after the API suite expanded to cover malformed `start_date`, malformed `frustration_min`, and malformed `grade_id` parsing in addition to the previously covered monitoring route contract cases.
- `P2.6.17` (`EDA-167`) approved after unrestricted rerun of the full monitoring verification bundle passed with `34 passed`.
- `P2.6.18` (`EDA-168`) approved after the docs were synchronized with the review-fix outcome and the Phase 7 QA handoff state.
- Phase 6 is complete; the next step is Phase 7 end-to-end QA/hardening across monitoring, graded metrics, and the preserved legacy full-conversation route.

### Stream D Acceptance Criteria
- [x] Monitoring routes are protected and registered without altering legacy conversation-route semantics.
- [x] API tests cover auth, validation, empty-state, populated-state, and not-found contracts.
- [x] Compile and targeted pytest verification are executed or blockers are explicitly documented.
- [x] Docs remain synchronized with Phase 6 execution and Phase 7 handoff state.

## Suggested Files by Concern
- Config and constants:
  - `app/core/constants.py`
  - `app/core/config.py`
  - `.env.example`
- Models / migrations:
  - `app/models/conversation_grades.py`
  - `app/models/monitoring_highlight_config.py`
  - `alembic/versions/*.py` (conditional)
- Schemas:
  - `app/schemas/grading_monitoring.py` (new)
  - `app/schemas/__init__.py`
- Services:
  - `app/services/grading_monitoring.py` (new)
  - `app/services/monitoring_highlights.py` (new)
  - `app/services/grading_extraction.py` (reuse helpers only if needed)
  - `app/services/conversations.py` (reuse key helpers only if needed)
  - `app/services/__init__.py`
- Routes:
  - `app/api/routes/grading_monitoring.py` (new)
  - `app/api/routes/__init__.py`
  - `app/api/router.py`
- Tests:
  - `tests/test_monitoring_highlights.py` (new)
  - `tests/test_grading_monitoring.py` (new)
  - `tests/test_grading_monitoring_api.py` (new)
  - `tests/test_grading_config.py`
  - `tests/test_grading_schemas.py`
  - `tests/test_conversations_api.py` / `tests/test_conversations_service.py` only if preserved full-conversation linkage needs regression coverage

## Component Dependency Summary
- Gate 6.0 defines route strategy, any conditional read indexes, monitoring settings, schemas, and scaffolds.
- Stream A should land first because both the list and detail experiences depend on one shared highlight evaluator.
- Stream B and Stream C can run in parallel after Stream A because list and detail operate on separate service paths once highlight evaluation is available.
- Stream D depends on B/C so the route layer exposes real list/detail monitoring behavior instead of placeholders.
- Phase 7 should validate both the new monitoring surface and the preserved legacy/full-conversation contracts together.

## Parallelization Map

```text
Gate 6.0 (P2.6.1 - P2.6.5 monitoring contract + readiness) -------+
                                                                     |
  |- Stream A (highlight config + evaluator) ---------------------> |
                                                                     |
  |- Stream B (monitoring list) ---------------------------------> |  (after A)
  |- Stream C (detail + timeline + conversation link) -----------> |  (after A)
                                                                     |
  |- Stream D (API + tests + QA + docs) -------------------------> |  (after B/C)
                                                                     v
             Phase 6 Complete (Conversations Monitoring API Overhaul)
```

## Definition of Done (Phase 6)
- [x] New monitoring endpoints exist under `/api/v1/monitoring/conversations`.
- [x] Monitoring list is customer-day grade driven, server-side filtered/sorted/paginated, and highlight-aware.
- [x] Monitoring detail combines same-day transcript, grouped grade panel, and recent grade-history timeline.
- [x] Existing `/api/v1/conversations/{conversation_key}/messages` remains the preserved full-conversation surface across time.
- [x] Highlights are computed on read from configurable rules with stable fallback behavior.
- [x] Targeted highlight, monitoring service, and monitoring API tests exist for the modified scope.
- [x] No lint/syntax errors exist in modified Python modules.

## Test Scenarios (Phase 6 Validation)

### Happy Path
- Monitoring list returns customer-day rows for the previous GST day with canonical intent metadata and highlight badges.
- Monitoring list filters by escalation type, resolution, frustration threshold, accuracy threshold, and intent codes correctly.
- Monitoring detail returns same-day transcript messages ordered chronologically plus the full grouped grade panel.
- Monitoring detail includes recent grade-history points for the same canonical identity and a `conversation_key` that opens the existing full-conversation route.

### Edge Cases
- Empty monitoring window returns `items=[]`, `total=0`, stable paging metadata, and independent freshness metadata.
- Missing active highlight config falls back to seeded defaults without failing the response.
- Invalid date windows, unsupported sort fields/directions, and invalid intent filters return stable validation error envelopes.
- Detail lookup for an unknown `grade_id` returns a stable not-found contract.
- A customer-day with no same-day messages should be treated as data corruption/not-found for detail loading rather than returning a partial payload.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- Existing `/api/v1/conversations/{conversation_key}/messages` is sufficient as the preserved full-conversation view across time.
- Monitoring list defaults to the previous GST day because daily grading is the primary analyst triage workflow.
- Current-rules highlight semantics are acceptable until config versioning exists.
- CSV export of filtered monitoring results remains deferred beyond Phase 6.
- Tenant-scoped monitoring remains out of scope for Milestone 2, so the authenticated-any-role baseline is acceptable for now.

### Open Questions
- None currently. Gate 6.0 resolves the previously deferred route-strategy and historical-highlight semantics for Phase 6 planning.

## Estimated Duration (Units)
- Gate 6.0 (`P2.6.1` - `P2.6.5`): `2.25`
- Stream A (`P2.6.6` - `P2.6.8`): `1.25`
- Stream B (`P2.6.9` - `P2.6.11`): `1.5`
- Stream C (`P2.6.12` - `P2.6.14`): `1.5`
- Stream D (`P2.6.15` - `P2.6.18`): `1.25`
- Sequential total: `7.75`
- Parallelized total after Gate (A, then B/C concurrent, then D): `~5.75 - 6.25`

## Done Condition for Phase 6 Planning
Phase 6 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-6.md`).
- `docs/tasks.md` includes Phase 6 task entries aligned with this plan.
- `docs/project-progress.md` reflects Phase 6 as the active planned phase and records that Kanban task creation remains deferred unless explicitly requested.
- Kanban task creation remains deferred unless explicitly requested.
