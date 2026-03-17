# Milestone 2 - Phase 7 Plan: AI Agent Performance Dashboard API

## Goals
- Deliver dedicated dashboard endpoints for the three views defined in `docs/dashboard_spec.md` without mutating the existing Phase 5 metrics or Phase 6 monitoring route contracts.
- Expose view-shaped backend payloads for Agent Pulse, Correlations, and Daily Timeline so the frontend does not need to reconstruct heavy aggregates client-side.
- Reuse stabilized Milestone 2 semantics from `conversation_grades`, `grading_runs`, and Phase 6 conversation linkage instead of inventing a second analytics model.
- Keep the three view implementations parallelizable by giving each view its own service/test surface after a shared Gate 7.0 contract pass.
- Leave Phase 7 in a reviewable state with deterministic service and API tests plus a clean handoff into Phase 8 milestone-wide QA/hardening.

## Planning Analysis (Required Order)

### 1) Data Models
- `conversation_grades` remains the primary Phase 7 fact table.
  - Agent Pulse and Correlations should read only from graded customer-day rows plus shared Phase 4 freshness metadata.
  - Composite "overall" performance should be derived from the five AI Performance dimensions on each row (`relevancy_score`, `accuracy_score`, `completeness_score`, `clarity_score`, `tone_score`).
- `grading_runs` remains a secondary read source for freshness metadata only.
  - Dashboard freshness should reuse the latest-successful semantics already established in Phase 5 (`completed` and `completed_with_failures`).
  - Dashboard endpoints must not derive visual aggregates from run counters.
- Raw chat timestamps are required for the Daily Timeline hourly view.
  - `conversation_grades.created_at` reflects grade-row insertion time, not analyst-facing conversation activity time.
  - Hour bucketing for Daily Timeline should therefore reuse same-day raw-chat joins via canonical identity + GST `grade_date`, using the Phase 3/6 extraction helpers and raw message timestamps.
- Existing service logic should be reused where it preserves a single source of truth:
  - Phase 5 metrics helpers for zero-filled date windows, intent metadata, and freshness semantics
  - Phase 6 monitoring/conversation helpers for `conversation_key` linkage and same-day raw-chat joins
- Phase 7 should add three view-shaped response families:
  - Agent Pulse: overall score ring, dimension bars, health chips, escalation strip, user signals, trend series, top intents, attention signals, freshness
  - Correlations: performance-vs-satisfaction heatmap, failure funnel, frustration histogram, story cards, freshness
  - Daily Timeline: hourly heatmap, best/worst hour summaries, scatter dataset, worst-performers rows, drill-down linkage metadata, freshness

### 2) Migration
- Default path: no migration unless dashboard-specific read plans reveal a clear gap.
- Gate validation should confirm read readiness for:
  - bounded `grade_date` window filters
  - grouped heatmap and histogram bucket queries over `satisfaction_score`, `frustration_score`, `loop_detected`, and `escalation_type`
  - daily low-composite ranking for worst-performer rows
  - same-day raw-chat joins driven by canonical identity + GST `grade_date`
- If additive read indexes are required, Phase 7 may add only bounded `conversation_grades` indexes, for example:
  - `conversation_grades(grade_date, satisfaction_score)`
  - `conversation_grades(grade_date, loop_detected, escalation_type)`
- Phase 7 should not:
  - alter raw chat table structure
  - add linkage columns or foreign keys to raw chats
  - introduce materialized views in the first pass
- Performance escalation beyond bounded indexes should be deferred to Phase 8 hardening or a later milestone if real query evidence justifies it.

### 3) Dependencies
- Upstream dependencies satisfied:
  - Phase 1 canonical identity, intent taxonomy, and highlight label registries
  - Phase 3 and 3.5 grading output, transcript selectors, and canonical customer-day semantics
  - Phase 4 latest-successful run freshness model
  - Phase 5 graded metrics query and zero-fill semantics
  - Phase 6 monitoring conversation linkage and same-day transcript join helpers
- Phase 7 must preserve existing route contracts:
  - `/api/v1/analytics/*` remains Milestone 1 raw-chat analytics
  - `/api/v1/grading/metrics/*` remains the reusable graded metrics surface
  - `/api/v1/monitoring/conversations/*` remains the analyst monitoring surface
- The new dashboard routes should behave as a backend-for-frontend layer over stabilized Phase 5/6 semantics, not as a replacement for those reusable APIs.

### 4) Configuration
- Phase 7 should add bounded dashboard query settings:
  - default dashboard window: previous 7 GST days ending on the previous GST day
  - maximum dashboard window: 31 GST days
  - default Daily Timeline target date: previous GST day
  - default worst-performers limit: 10
  - maximum worst-performers limit: 50
- Shared dashboard bucket and threshold registries should be centralized so schemas, services, and tests do not drift on:
  - Agent Pulse attention-signal thresholds
  - Correlations heatmap score buckets (`1-4`, `5-7`, `8-10`)
  - frustration histogram buckets (`1-2`, `3-4`, `5-6`, `7-8`, `9-10`)
  - story-card severity thresholds
- Config validation should fail fast for invalid dashboard bounds the same way the Phase 5 and Phase 6 settings do.

### 5) Endpoints
- Planned additive route group: `/api/v1/grading/dashboard`
- Planned Phase 7 endpoints:
  - `GET /api/v1/grading/dashboard/agent-pulse`
    - bounded window summary for the Agent Pulse tab
    - response includes trend series, top intents, attention signals, and freshness
  - `GET /api/v1/grading/dashboard/correlations`
    - bounded window correlations payload for the Correlations tab
    - response includes heatmap cells, funnel steps, histogram buckets, story cards, and freshness
  - `GET /api/v1/grading/dashboard/daily-timeline`
    - single-date operational payload for the Daily Timeline tab
    - response includes 24 hourly buckets, best/worst hour, scatter points, worst performers, drill-down IDs, and freshness
- Access baseline for Phase 7:
  - `super_admin`: allowed
  - `company_admin`: allowed
  - `analyst`: allowed

## Dependencies
- Phase dependency: `Milestone 2 Phase 6 complete -> Milestone 2 Phase 7`
- Downstream impact:
  - Phase 8 QA should validate the new dashboard routes alongside the already-shipped Phase 5 metrics, Phase 6 monitoring, and preserved `/api/v1/conversations/{conversation_key}/messages` surface.
  - Frontend dashboard work can build directly against one backend contract per view instead of recombining multiple lower-level APIs.

## Phase 7 Contract Outline (Planning Baseline)

### Route Strategy
- Add dashboard routes under `/api/v1/grading/dashboard/*`.
- Keep the Phase 5 and Phase 6 route groups unchanged in meaning.
- The dashboard endpoints are backend-for-frontend payloads for the three documented views, not a replacement for the reusable metrics and monitoring surfaces.

### Agent Pulse Semantics
- Query uses a bounded GST date window (`start_date`, `end_date`) with a default 7-day window ending on the previous GST day.
- Response should include:
  - selected date window
  - overall composite score
  - per-dimension averages for the five AI Performance dimensions
  - health chips for `resolution_rate_pct`, `avg_repetition_score`, and `loop_detected_rate_pct`
  - escalation distribution split across `Natural`, `Failure`, and `None`
  - user signals (`avg_satisfaction_score`, `avg_frustration_score`, `user_relevancy_rate_pct`)
  - daily trend points for overall, satisfaction, and frustration across the selected window
  - top intent tags with canonical metadata and counts
  - derived attention signals with stable severity ordering
  - freshness metadata
- Empty windows should remain schema-stable with zero-valued aggregates, empty intent tags, no attention signals, and independent freshness metadata when successful grading runs exist.

### Correlations Semantics
- Query uses the same bounded GST date window as Agent Pulse.
- Response should include:
  - 5 x 3 heatmap cells for the five AI Performance dimensions crossed with score buckets (`1-4`, `5-7`, `8-10`)
  - failure funnel counts for:
    - total graded customer-days
    - loop detected
    - frustration score >= configured threshold
    - unresolved
    - escalation type = `Failure`
  - fixed frustration histogram buckets
  - exactly four story cards with deterministic severity, metric, and explanation fields derived from the selected window
  - freshness metadata
- Heatmap and histogram responses should be zero-filled so the frontend never has to infer missing buckets.

### Daily Timeline Semantics
- Query uses one `target_date` plus an optional bounded `worst_performers_limit`.
- Hourly bucket calculations must use same-day raw chat timestamps joined to graded rows through canonical identity + GST `grade_date`.
- Response should include:
  - selected target date
  - 24 GST hourly buckets with:
    - hour
    - conversation volume
    - resolution rate
  - best hour and worst hour summaries derived from non-empty buckets
  - scatter points for satisfaction vs frustration, with `resolution`, `loop_detected`, `grade_id`, and optional drill-down linkage metadata
  - worst-performers table rows ordered by lowest composite score for the target date, including:
    - `grade_id`
    - `conversation_key`
    - contact label
    - five AI Performance scores
    - satisfaction, frustration, resolution, escalation type, intent metadata
  - freshness metadata
- If a target date has no graded rows, the endpoint should still return 24 zero-filled hourly buckets, empty scatter/worst-performer arrays, null best/worst-hour summaries, and independent freshness metadata.

### Freshness Semantics
- All three dashboard endpoints should expose the latest-successful grading freshness metadata used in Phase 5.
- Freshness remains derived from `grading_runs`, not from raw chat timestamps or grade-row insert timestamps.

## Gate 7.0 - Dashboard Contract and Readiness

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 7.0.1 | `P2.7.1 - Design - Finalize dashboard route strategy, window semantics, and access matrix - Gate (Independent)` | Lock the additive dashboard route group, per-view endpoint split, GST window defaults, access baseline, and the rule that Daily Timeline hour bucketing uses raw chat timestamps instead of `conversation_grades.created_at`. | None | `docs/milestone-2/m2-phase-7.md`, `docs/milestone-2/milestone-notes.md` | Review checklist confirms route semantics, window rules, and access behavior are explicit and stable. |
| 7.0.2 | `P2.7.2 - DB - Validate dashboard read-path readiness and add additive grade indexes if needed - Gate (Dependent)` | Confirm dashboard aggregates are read-ready for window, bucket, and worst-performer queries; add bounded `conversation_grades` indexes only if actual gaps exist. | `P2.7.1` | `app/models/conversation_grades.py`, `alembic/versions/*.py` (conditional) | Migration smoke if a revision is added; no raw-chat schema changes. |
| 7.0.3 | `P2.7.3 - Config - Add dashboard window, bucket, and limit settings plus threshold registries - Gate (Dependent)` | Add bounded dashboard defaults and shared threshold registries for attention signals, story cards, heatmap buckets, and worst-performer limits. | `P2.7.1` | `app/core/constants.py`, `app/core/config.py`, `.env.example`, `tests/test_grading_config.py` | Config validation tests for window bounds, limit bounds, and threshold registry drift. |
| 7.0.4 | `P2.7.4 - API - Define shared dashboard query schemas, view payloads, and error envelopes - Gate (Dependent)` | Add typed query/error/common schemas plus view response contracts for Agent Pulse, Correlations, and Daily Timeline. | `P2.7.1`, `P2.7.3` | `app/schemas/grading_dashboard_common.py` (new), `app/schemas/grading_dashboard_agent_pulse.py` (new), `app/schemas/grading_dashboard_correlations.py` (new), `app/schemas/grading_dashboard_daily_timeline.py` (new), `app/schemas/__init__.py`, `tests/test_grading_schemas.py` | Schema validation tests and import/OpenAPI smoke checks. |
| 7.0.5 | `P2.7.5 - Service - Scaffold dashboard service boundaries for per-view parallel work - Gate (Dependent)` | Create shared module/export boundaries so each dashboard view can be implemented independently after Gate 7.0. | `P2.7.2`, `P2.7.4` | `app/services/grading_dashboard_agent_pulse.py` (new), `app/services/grading_dashboard_correlations.py` (new), `app/services/grading_dashboard_daily_timeline.py` (new), `app/services/__init__.py`, `tests/test_grading_dashboard_scaffold.py` (new) | Compile/import smoke confirms the new modules are discoverable and non-circular. |

### P2.7.1 Decision Record - Dashboard Route Strategy, Window Semantics, and Access

#### Decision Summary
- Phase 7 introduces additive dashboard endpoints under `/api/v1/grading/dashboard/*`.
- The dashboard contract is one endpoint per documented view:
  - `agent-pulse`
  - `correlations`
  - `daily-timeline`
- Dashboard endpoints are backend-for-frontend payloads that reuse Phase 5/6 semantics rather than replacing those reusable route groups.
- Daily Timeline hour bucketing uses same-day raw chat timestamps joined through canonical identity + `grade_date`, not `conversation_grades.created_at`.
- Phase 7 access stays aligned with the current authenticated analytics/metrics/monitoring baseline: any active role may read dashboard data.

#### Access Matrix

| Endpoint / Action | `super_admin` | `company_admin` | `analyst` |
|---|---|---|---|
| `GET /api/v1/grading/dashboard/agent-pulse` | allowed | allowed | allowed |
| `GET /api/v1/grading/dashboard/correlations` | allowed | allowed | allowed |
| `GET /api/v1/grading/dashboard/daily-timeline` | allowed | allowed | allowed |

#### Window and Date Rules
- Agent Pulse and Correlations use:
  - `end_date = previous GST day` by default
  - `start_date = end_date - 6 days` by default
  - maximum span = configured dashboard max window
- Daily Timeline uses:
  - `target_date = previous GST day` by default
  - `worst_performers_limit = 10` by default
  - maximum worst-performers limit = configured dashboard max

#### Why Phase 7 Adds a Dashboard-Specific Route Group
- Phase 5 and Phase 6 already provide reusable lower-level surfaces with stable semantics.
- The dashboard views need heavier, view-shaped payloads and derived insight heuristics that would be awkward to reconstruct from multiple client calls.
- A dedicated dashboard BFF keeps frontend contracts simple while preserving the reusable APIs underneath.

### P2.7.2 Readiness Decision - Dashboard Read Path and Index Coverage

#### Decision Summary
- No new Phase 7 Alembic revision is required at Gate 7.0.
- The current `conversation_grades` read path is already bounded enough for the planned dashboard queries:
  - `ix_conversation_grades_grade_date` covers the shared date-window filter used by Agent Pulse and Correlations.
  - `ix_conversation_grades_grade_date_escalation_type`, `ix_conversation_grades_grade_date_resolution`, `ix_conversation_grades_grade_date_frustration_score`, and `ix_conversation_grades_grade_date_accuracy_score` already cover the secondary fields most likely to affect the dashboard funnel, health, and ranking slices.
  - `uq_conversation_grades_identity_day` already supports the canonical identity + `grade_date` lookup path needed when Daily Timeline joins graded rows back to same-day raw chat activity.
- The remaining planned dashboard reads are bounded aggregates or per-day rankings, so adding new speculative indexes now would overfit an implementation that has not yet produced real query evidence.

#### Explicit Non-Changes
- No raw chat schema changes.
- No new linkage columns or foreign keys.
- No materialized views.
- No new `conversation_grades` indexes until Phase 7 implementation produces actual query evidence that the existing bounded read path is insufficient.

### Gate 7.0 Acceptance Criteria
- [x] Phase 7 uses an additive dashboard route group rather than mutating the existing Phase 5 or Phase 6 route contracts.
- [x] Agent Pulse and Correlations share one bounded window contract with explicit defaults and limits.
- [x] Daily Timeline explicitly uses same-day raw chat timestamps for hourly bucketing.
- [x] Typed query/response/error schemas exist for all three dashboard views.
- [x] Service module boundaries are established so Streams A-C can run in parallel with minimal file overlap.

### Gate 7.0 Execution Status (`2026-03-17`)
- `P2.7.1` (`EDA-169`) was already satisfied by the existing Phase 7 planning docs and was reconciled to `IN REVIEW` on Kanban.
- `P2.7.2` (`EDA-170`) recorded a no-migration decision because the existing bounded `conversation_grades` indexes were sufficient for the planned dashboard reads; the task moved to `DONE`.
- `P2.7.3` (`EDA-171`) added dashboard defaults/registries in `app/core/constants.py`, `app/core/config.py`, `app/core/__init__.py`, `.env.example`, and `tests/test_grading_config.py`; the task moved to `IN REVIEW`.
- `P2.7.4` (`EDA-173`) added the shared/common plus per-view dashboard schema modules and exports in `app/schemas/*`, with coverage extended in `tests/test_grading_schemas.py`; the task moved to `IN REVIEW`.
- `P2.7.5` (`EDA-172`) added per-view dashboard service scaffolds and exports in `app/services/*`, with import smoke coverage in `tests/test_grading_dashboard_scaffold.py`; the task moved to `IN REVIEW`.
- Gate 7.0 verification:
  - `python -m compileall app/core/constants.py app/core/config.py app/core/__init__.py app/schemas/grading_dashboard_common.py app/schemas/grading_dashboard_agent_pulse.py app/schemas/grading_dashboard_correlations.py app/schemas/grading_dashboard_daily_timeline.py app/schemas/__init__.py app/services/grading_dashboard_agent_pulse.py app/services/grading_dashboard_correlations.py app/services/grading_dashboard_daily_timeline.py app/services/__init__.py tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_dashboard_scaffold.py` passed.
  - `pytest tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_dashboard_scaffold.py -q` passed (`52 passed`).

### Gate 7.0 Review-Fix Status (`2026-03-17`)
- `P2.7.3` (`EDA-171`) review fix:
  - tightened `app/core/config.py` so dashboard window settings cannot exceed `31` days and dashboard worst-performer limit settings cannot exceed `50`, even when callers try to raise both the default and max values together.
  - extended `tests/test_grading_config.py` with regression coverage for rejecting `dashboard_max_window_days > 31` and `dashboard_max_worst_performers_limit > 50`.
- `P2.7.4` (`EDA-173`) required no additional code changes in the review-fix pass because its only review finding was the upstream config-bound issue from `EDA-171`.
- `P2.7.5` (`EDA-172`) required no additional code changes in the review-fix pass because its only review finding was the same upstream config-bound issue from `EDA-171`.
- Review-fix verification:
  - `python -m compileall app/core/config.py tests/test_grading_config.py app/schemas/grading_dashboard_common.py app/schemas/grading_dashboard_agent_pulse.py app/schemas/grading_dashboard_correlations.py app/schemas/grading_dashboard_daily_timeline.py tests/test_grading_schemas.py app/services/grading_dashboard_agent_pulse.py app/services/grading_dashboard_correlations.py app/services/grading_dashboard_daily_timeline.py tests/test_grading_dashboard_scaffold.py` passed.
  - `pytest tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_dashboard_scaffold.py -q` passed (`54 passed`).

## Stream A - Agent Pulse View

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.7.6 - Service - Implement Agent Pulse composite, dimension, and health aggregates - Stream A (Dependent)` | Build the core Agent Pulse summary payload: overall composite, dimension averages, health chips, escalation strip, and user-signal cards for a bounded window. | `P2.7.5` | `app/services/grading_dashboard_agent_pulse.py`, `app/services/grading_metrics.py` (reuse only if needed) | Service tests for populated and empty windows plus rate/average correctness. |
| A.2 | `P2.7.7 - Service - Add Agent Pulse trends, top intents, freshness, and attention signals - Stream A (Dependent)` | Extend Agent Pulse with daily trend series, top intent tags, latest-successful freshness, and deterministic attention signals derived from shared thresholds. | `P2.7.6` | `app/services/grading_dashboard_agent_pulse.py`, `app/core/constants.py` (reuse only if threshold helpers are needed) | Tests for zero-filled trends, intent ordering, freshness fallback, and attention-signal severity ordering. |
| A.3 | `P2.7.8 - Test - Add deterministic Agent Pulse service tests - Stream A (Dependent)` | Add focused coverage for populated windows, empty windows, derived attention signals, and freshness behavior. | `P2.7.7` | `tests/test_grading_dashboard_agent_pulse.py` (new) | `pytest tests/test_grading_dashboard_agent_pulse.py -q`. |

### Stream A Acceptance Criteria
- [x] Agent Pulse aggregates are computed from graded customer-day rows with no client-side reconstruction required.
- [x] Trend data is zero-filled across the selected window and freshness remains independent from empty-window aggregates.
- [x] Intent tags expose canonical intent metadata only.
- [x] Attention signals are deterministic, threshold-driven, and returned in stable severity order.

### Stream A Execution Status (`2026-03-17`)
- `P2.7.6` implemented the Agent Pulse aggregate payload in `app/services/grading_dashboard_agent_pulse.py`, including the overall composite score, five AI-dimension averages, health cards, escalation strip, and user-signal cards over a bounded dashboard window.
- `P2.7.7` extended the same service with zero-filled daily trend points, canonical top-intent tags capped to the documented six-row slice, latest-successful freshness metadata, and deterministic attention signals with stable priority ordering.
- `P2.7.8` added `tests/test_grading_dashboard_agent_pulse.py` with focused coverage for populated windows, empty windows, trend zero fill, top-intent ordering/limit behavior, freshness fallback, and attention-signal ordering.
- Validation:
  - `pytest tests/test_grading_dashboard_agent_pulse.py -q` passed (`4 passed`).
  - `C:\Users\Public\anaconda3\python.exe -m compileall app/services/grading_dashboard_agent_pulse.py tests/test_grading_dashboard_agent_pulse.py` passed.

## Stream B - Correlations View

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.7.9 - Service - Implement Correlations heatmap and failure funnel aggregates - Stream B (Dependent)` | Build the windowed heatmap cells and sequential failure-funnel counts for the Correlations tab. | `P2.7.5` | `app/services/grading_dashboard_correlations.py` | Service tests for zero-filled heatmap buckets and monotonic funnel counts. |
| B.2 | `P2.7.10 - Service - Add frustration histogram and derived story-card insights - Stream B (Dependent)` | Add fixed frustration histogram buckets plus exactly four server-generated story cards with stable severity and explanation fields. | `P2.7.9` | `app/services/grading_dashboard_correlations.py`, `app/core/constants.py` (reuse only if severity thresholds are needed) | Tests for histogram bucket coverage, story-card ordering, and empty-window insight fallback behavior. |
| B.3 | `P2.7.11 - Test - Add deterministic Correlations service tests - Stream B (Dependent)` | Add focused coverage for heatmap, funnel, histogram, and story-card derivation across populated and sparse windows. | `P2.7.10` | `tests/test_grading_dashboard_correlations.py` (new) | `pytest tests/test_grading_dashboard_correlations.py -q`. |

### Stream B Acceptance Criteria
- [ ] Heatmap payloads return every dimension x bucket combination with stable zero-fill behavior.
- [ ] Failure funnel counts respect the documented sequential filter path and never invert unexpectedly.
- [ ] Frustration histogram bucket semantics are fixed and documented.
- [ ] Story cards are server-derived, deterministic, and bounded to the documented four-card contract.

### Stream B Execution Status (`2026-03-17`)
- `P2.7.9` completed and moved to `IN REVIEW`:
  - `app/services/grading_dashboard_correlations.py` now returns the bounded Correlations heatmap with every dimension/bucket combination present plus the documented sequential failure funnel.
- `P2.7.10` completed and moved to `IN REVIEW`:
  - `app/services/grading_dashboard_correlations.py` now adds fixed frustration histogram buckets and exactly four derived story cards sorted by severity first, then by the fallback priority order.
- `P2.7.11` completed and moved to `IN REVIEW`:
  - `tests/test_grading_dashboard_correlations.py` now covers empty-window zero fill, populated heatmap cells, sequential funnel monotonicity, histogram buckets, and story-card ordering/fallback behavior.
- Stream B verification:
  - `python -m compileall -f app/services/grading_dashboard_correlations.py tests/test_grading_dashboard_correlations.py` passed.
  - `pytest tests/test_grading_dashboard_correlations.py -q` passed (`5 passed`).

## Stream C - Daily Timeline View

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.7.12 - Service - Implement Daily Timeline hourly heatmap and best/worst-hour summaries from same-day raw chat timestamps - Stream C (Dependent)` | Build 24 GST hourly buckets plus best/worst-hour summaries using same-day raw chat timestamps joined through canonical identity + `grade_date`. | `P2.7.5` | `app/services/grading_dashboard_daily_timeline.py`, `app/services/grading_extraction.py` (reuse helpers only as needed), `app/services/grading_monitoring.py` (reuse join helpers only as needed) | Service tests for 24-bucket zero fill, hour ordering, and correct rejection of `conversation_grades.created_at` as the hour source. |
| C.2 | `P2.7.13 - Service - Add Daily Timeline scatter dataset, worst-performers table, and drill-down linkage metadata - Stream C (Dependent)` | Add per-grade scatter points plus bounded worst-performer rows carrying `grade_id`, `conversation_key`, and canonical intent/outcome metadata for drill-down flows. | `P2.7.12` | `app/services/grading_dashboard_daily_timeline.py`, `app/services/conversations.py` (reuse key helpers only as needed) | Tests for scatter payload shape, worst-performer ordering, limit enforcement, and stable linkage metadata. |
| C.3 | `P2.7.14 - Test - Add deterministic Daily Timeline service tests - Stream C (Dependent)` | Cover zero-filled day windows, populated hourly aggregation, scatter point contracts, worst-performer ranking, and drill-down IDs. | `P2.7.13` | `tests/test_grading_dashboard_daily_timeline.py` (new) | `pytest tests/test_grading_dashboard_daily_timeline.py -q`. |

### Stream C Acceptance Criteria
- [x] Daily Timeline hour bucketing is driven by same-day raw chat timestamps, not grade-row insertion timestamps.
- [x] Hourly output always returns all 24 GST hours in order.
- [x] Scatter points and worst-performer rows carry the IDs the frontend needs for drill-down into monitoring or full-conversation views.
- [x] Empty days remain schema-stable with zero-filled hourly buckets and empty drill-down collections.

### Stream C Execution Status (`2026-03-17`)
- `P2.7.12` completed and moved to `IN REVIEW`:
  - `app/services/grading_dashboard_daily_timeline.py` now builds 24 GST hourly buckets via a two-query Python-merge approach: an inner subquery extracts canonical identity + `created_at` for same-day chat messages, an outer GROUP BY produces the first-message timestamp per customer-day, and Python merges these with grade rows. Hour is taken directly from the stored Dubai-local `created_at.hour`, not from `conversation_grades.created_at`.
  - Grades without matching same-day chat activity are excluded from hourly counts but still appear in scatter points.
- `P2.7.13` completed and moved to `IN REVIEW`:
  - Scatter points cover all grade rows for the target date where both satisfaction and frustration scores are present; `grade_id` and `conversation_key` are included for drill-down.
  - Worst performers are loaded via a SQL query with correlated contact-label subquery, ordered by ascending composite AI score sum, bounded by `worst_performers_limit`, and carry canonical intent metadata.
- `P2.7.14` completed and moved to `IN REVIEW`:
  - `tests/test_grading_dashboard_daily_timeline.py` (17 tests) covers zero-filled empty days, hourly bucket ordering, raw-chat-timestamp sourcing (not grade `created_at`), first-message bucket assignment, multi-hour spread, resolution-rate calculation, scatter point inclusion/exclusion, worst-performer ranking/limit/skip/intent/contact-label, freshness independence, and 24-element stability.
- Stream C verification:
  - `python -m compileall app/services/grading_dashboard_daily_timeline.py tests/test_grading_dashboard_daily_timeline.py` passed.
  - `pytest tests/test_grading_dashboard_daily_timeline.py -q` passed (`17 passed`).
  - Full Gate 7.0 + Stream C slice: `pytest tests/test_grading_dashboard_scaffold.py tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_dashboard_daily_timeline.py -q` passed (`71 passed`).

### Stream C Review-Fix Status (`2026-03-17`)
- `P2.7.12` (`EDA-174`) review fix:
  - `app/services/grading_extraction.py` now exposes shared SQL reporting helpers for both date and hour derivation, and `app/services/grading_dashboard_daily_timeline.py` now uses that shared hour helper when bucketing the first same-day chat message.
  - The Daily Timeline service no longer mixes the SQL day filter with a separate Python UTC-to-GST hour conversion, so boundary timestamps stay internally consistent.
- `P2.7.13` (`EDA-175`) required no direct code changes in the review-fix pass because its rereview blocker was entirely upstream in the shared Daily Timeline timezone-alignment logic.
- `P2.7.14` (`EDA-176`) review fix:
  - `tests/test_grading_dashboard_daily_timeline.py` now adds a boundary regression for `2026-03-09 21:30:00` and realigns the hourly expectations to the shared SQL reporting-hour semantics used by the same-day filter.
- Review-fix verification:
  - `python -m compileall app/services/grading_extraction.py app/services/grading_dashboard_daily_timeline.py tests/test_grading_dashboard_daily_timeline.py` passed.
  - `pytest tests/test_grading_dashboard_daily_timeline.py -q` passed (`19 passed`).
  - `pytest tests/test_grading_dashboard_scaffold.py tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_dashboard_daily_timeline.py -q` passed (`73 passed`).

### Stream C Review Outcome (`2026-03-17`)
- Approved and moved to `DONE`:
  - `P2.7.12` (`EDA-174`)
  - `P2.7.13` (`EDA-175`)
  - `P2.7.14` (`EDA-176`)
- Rereview outcomes:
  - `P2.7.12` (`EDA-174`): the shared SQL reporting helpers now drive both same-day filtering and first-message hour bucketing, so the Daily Timeline service no longer drifts on boundary timestamps.
  - `P2.7.13` (`EDA-175`): no separate scatter-point or worst-performer defect surfaced after the upstream day/hour alignment fix landed, and the drill-down payload remained stable.
  - `P2.7.14` (`EDA-176`): the Daily Timeline test module now protects the `2026-03-09 21:30:00` boundary case alongside the broader hourly, scatter, worst-performer, and empty-day coverage.
- Review verification:
  - `python -m compileall app/services/grading_extraction.py app/services/grading_dashboard_daily_timeline.py tests/test_grading_dashboard_daily_timeline.py` passed.
  - `pytest tests/test_grading_dashboard_daily_timeline.py -q` passed (`19 passed`).
  - `pytest tests/test_grading_dashboard_scaffold.py tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_dashboard_daily_timeline.py -q` passed (`73 passed`).

## Stream D - API, Validation, and Phase 8 Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.7.15 - API - Add protected dashboard view endpoints - Stream D (Dependent)` | Implement the `/api/v1/grading/dashboard/*` route group and register the three dashboard view endpoints cleanly. | `P2.7.8`, `P2.7.11`, `P2.7.14` | `app/api/routes/grading_dashboard.py` (new), `app/api/routes/__init__.py`, `app/api/router.py` | Route import/OpenAPI smoke checks and direct handler validation. |
| D.2 | `P2.7.16 - Test - Add dashboard API tests for auth, validation, empty-state, and populated payload contracts - Stream D (Dependent)` | Cover auth behavior, invalid windows/dates/limits, empty states, and populated Agent Pulse, Correlations, and Daily Timeline responses. | `P2.7.15` | `tests/test_grading_dashboard_api.py` (new), `tests/conftest.py` (fixture extensions if needed) | `pytest tests/test_grading_dashboard_api.py -q`. |
| D.3 | `P2.7.17 - QA - Run compile and targeted pytest verification for dashboard scope - Stream D (Dependent)` | Execute compile and focused pytest verification for dashboard schemas, services, and routes. | `P2.7.16` | No mandatory code files; QA notes in task records | `python -m compileall app tests` and targeted dashboard pytest suites. |
| D.4 | `P2.7.18 - Docs - Update task/progress docs with Phase 7 execution notes and Phase 8 handoff risks - Stream D (Dependent)` | Sync docs after execution/review and capture any remaining dashboard/runtime risks for the final Milestone 2 hardening phase. | `P2.7.17` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-7.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Acceptance Criteria
- [x] Dashboard routes are protected and registered without mutating existing Phase 5 or Phase 6 route semantics.
- [x] API tests cover auth, validation, empty-state, and populated-state contracts for all three view endpoints.
- [x] Compile and targeted pytest verification are executed or blockers are explicitly documented.
- [x] Docs remain synchronized with Phase 7 execution outcomes and the Phase 8 handoff state.

### Stream D Execution Status (`2026-03-17`)
- `P2.7.15` (`EDA-177`) completed; review approved and moved to `DONE`:
  - `app/api/routes/grading_dashboard.py` (new) implements the `/api/v1/grading/dashboard/*` route group with three protected GET endpoints: `/agent-pulse`, `/correlations`, and `/daily-timeline`.
  - `app/api/routes/__init__.py` and `app/api/router.py` register the new `grading_dashboard_router` alongside the existing route groups.
  - `app/main.py` adds dashboard-specific validation error handling that classifies malformed date-window and worst-performers-limit payloads into the documented `GradingDashboardErrorCode` envelope.
- `P2.7.16` (`EDA-178`) rereview approved and moved to `DONE`:
  - `tests/test_grading_dashboard_api.py` (new, 17 tests) covers unauthenticated rejection for all three endpoints, role access for analyst/company_admin/super_admin, inverted-window and future-date validation, over-max and non-positive `worst_performers_limit` rejection with `invalid_limit` error code, empty-state zero-fill behavior, and populated-state payload contracts including trend points, heatmap cells, hourly buckets, scatter points, and worst-performer rows.
  - Review-fix: `_classify_dashboard_query_error` in `app/api/routes/grading_dashboard.py` now falls back to error-message matching when the model-level validator produces an empty `loc` tuple, so over-max `worst_performers_limit` errors are correctly classified as `invalid_limit` instead of `invalid_date_window`.
- `P2.7.17` (`EDA-179`) rereview approved and moved to `DONE`:
  - `python -m compileall` passed for all dashboard route, schema, service, and test files.
  - `pytest tests/test_grading_dashboard_api.py tests/test_grading_dashboard_scaffold.py tests/test_grading_dashboard_agent_pulse.py tests/test_grading_dashboard_correlations.py tests/test_grading_dashboard_daily_timeline.py tests/test_grading_config.py tests/test_grading_schemas.py -q` passed (`99 passed`).
- `P2.7.18` (`EDA-180`) remains `IN REVIEW`:
  - `docs/tasks.md`, `docs/project-progress.md`, and `docs/milestone-2/m2-phase-7.md` synchronized with Stream D rereview outcomes and Phase 8 handoff state.

## Suggested Files by Concern
- Config and constants:
  - `app/core/constants.py`
  - `app/core/config.py`
  - `.env.example`
- Models / migrations:
  - `app/models/conversation_grades.py`
  - `alembic/versions/*.py` (conditional)
- Schemas:
  - `app/schemas/grading_dashboard_common.py` (new)
  - `app/schemas/grading_dashboard_agent_pulse.py` (new)
  - `app/schemas/grading_dashboard_correlations.py` (new)
  - `app/schemas/grading_dashboard_daily_timeline.py` (new)
  - `app/schemas/__init__.py`
- Services:
  - `app/services/grading_dashboard_agent_pulse.py` (new)
  - `app/services/grading_dashboard_correlations.py` (new)
  - `app/services/grading_dashboard_daily_timeline.py` (new)
  - `app/services/grading_metrics.py` (reuse only where it preserves a single source of truth)
  - `app/services/grading_monitoring.py` (reuse join/link helpers only where needed)
  - `app/services/grading_extraction.py` (reuse canonical identity + GST selectors only where needed)
  - `app/services/__init__.py`
- Routes:
  - `app/api/routes/grading_dashboard.py` (new)
  - `app/api/routes/__init__.py`
  - `app/api/router.py`
- Tests:
  - `tests/test_grading_dashboard_scaffold.py` (new)
  - `tests/test_grading_dashboard_agent_pulse.py` (new)
  - `tests/test_grading_dashboard_correlations.py` (new)
  - `tests/test_grading_dashboard_daily_timeline.py` (new)
  - `tests/test_grading_dashboard_api.py` (new)
  - `tests/test_grading_config.py`
  - `tests/test_grading_schemas.py`
  - `tests/conftest.py` (if fixture extensions are needed)

## Component Dependency Summary
- Gate 7.0 defines the dashboard route strategy, any conditional read indexes, shared config/constants, view schemas, and service boundaries.
- Stream A, Stream B, and Stream C can run in parallel after Gate 7.0 because each one owns one dashboard view and its dedicated service/test surface.
- Stream D depends on A/B/C so the route layer exposes real dashboard payloads instead of placeholders.
- Phase 8 should validate both the new dashboard routes and the already-shipped Phase 5/6 routes they depend on.

## Parallelization Map

```text
Gate 7.0 (P2.7.1 - P2.7.5 dashboard contract + readiness) ----------+
                                                                      |
  |- Stream A (Agent Pulse view) ----------------------------------> |
  |- Stream B (Correlations view) ---------------------------------> |  (parallel after Gate)
  |- Stream C (Daily Timeline view) -------------------------------> |
                                                                      |
  |- Stream D (API + tests + QA + docs) ---------------------------> |  (after A/B/C)
                                                                      v
             Phase 7 Complete (AI Agent Performance Dashboard API)
```

## Definition of Done (Phase 7)
- [ ] New dashboard endpoints exist under `/api/v1/grading/dashboard/*`.
- [ ] Agent Pulse, Correlations, and Daily Timeline return stable view-shaped payloads that match `docs/dashboard_spec.md`.
- [ ] Daily Timeline hour bucketing is based on same-day raw chat timestamps joined to canonical graded customer-day rows.
- [ ] Existing `/api/v1/grading/metrics/*`, `/api/v1/monitoring/conversations/*`, and `/api/v1/conversations/{conversation_key}/messages` routes remain stable and unchanged in meaning.
- [ ] Targeted service and API tests exist for all three dashboard views.
- [ ] No lint/syntax errors exist in modified Python modules.

## Test Scenarios (Phase 7 Validation)

### Happy Path
- Agent Pulse returns populated composite, dimension, trend, intent, attention-signal, and freshness payloads for a 7-day window with graded rows.
- Correlations returns the complete heatmap, funnel, histogram, and four story cards for a populated date window.
- Daily Timeline returns 24 hourly buckets, best/worst hour summaries, scatter points, and worst-performer rows for a populated target date.
- Dashboard drill-down metadata (`grade_id`, `conversation_key`) opens the Phase 6 monitoring detail and preserved full-conversation views without a second identity scheme.

### Edge Cases
- Empty dashboard windows return stable zero-filled or empty payloads with independent freshness metadata when prior successful grading runs exist.
- Invalid or out-of-bounds date windows, malformed dates, and invalid worst-performer limits fail with stable dashboard validation error envelopes.
- Sparse data still returns complete heatmap and histogram bucket coverage rather than omitting missing combinations.
- Daily Timeline correctly ignores `conversation_grades.created_at` when raw chat timestamps and grade-row insert timestamps differ.
- Worst-performer ranking is stable when composite scores tie and the configured limit is hit.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- The frontend can consume one endpoint per dashboard view instead of stitching together multiple lower-level APIs.
- Story cards and attention signals can be derived from deterministic server-side thresholds without introducing a second LLM or free-text narrative generator.
- Bounded read queries are sufficient for the first implementation pass; materialized views remain unnecessary until real query evidence says otherwise.
- The Daily Timeline tab should favor operational truth from raw chat timestamps even though the broader dashboard is primarily grade-row-driven.

### Open Questions
- None currently. Phase 7 planning locks the view-per-endpoint strategy, raw-chat hour-source rule, and Phase 8 QA/hardening handoff direction.

## Estimated Duration (Units)
- Gate 7.0 (`P2.7.1` - `P2.7.5`): `2.5`
- Stream A (`P2.7.6` - `P2.7.8`): `1.5`
- Stream B (`P2.7.9` - `P2.7.11`): `1.5`
- Stream C (`P2.7.12` - `P2.7.14`): `1.75`
- Stream D (`P2.7.15` - `P2.7.18`): `1.25`
- Sequential total: `8.5`
- Parallelized total after Gate (A/B/C concurrent, then D): `~5.75 - 6.5`

## Done Condition for Phase 7 Planning
Phase 7 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-7.md`).
- `docs/tasks.md` includes Phase 7 task entries aligned to this plan.
- `docs/project-progress.md` reflects Phase 7 as the current planned phase and records that dashboard Kanban task creation remains deferred unless explicitly requested.
- Phase 8 is reserved for milestone-wide QA/hardening after dashboard implementation.
