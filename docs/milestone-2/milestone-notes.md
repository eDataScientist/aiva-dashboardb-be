# Milestone Planning Notes

This document captures milestone-level planning decisions made during discussions before detailed phase documents are written.

## Milestone 1 (Reference)
- Milestone 1 is complete (analytics backend foundation, async ORM services, and test infrastructure).
- Milestone 2 planning follows from the completed Milestone 1 backend baseline.

## Milestone 2 - Decisions Confirmed So Far

## Planning Scope and Style
- Use the term `Milestone 2` consistently.
- Milestone-level planning should stay high-level (phase goals and ordering only).
- Detailed design decisions, open questions, and implementation specifics belong in phase documents.

## Milestone 2 Scope Additions
- Milestone 2 includes a simple password authentication layer.
- Milestone 2 includes account profiles.

## Auth and Profile Decisions (Confirmed)
- Login uses `email + password`.
- Passwords are stored as a password hash only (no plaintext password storage).
- Phase 2 auth should use the simplest maintainable implementation path (current planning preference: JWT bearer auth unless a later constraint favors sessions).
- Account/profile data should live in a single table for Milestone 2 v1.
- Minimal profile scope for Milestone 2 v1 is `full_name` (plus core account/auth columns).
- Milestone 2 auth scope is login-only (no reset/change flow in scope).
- `company_admin` is role-only in Milestone 2 v1 (no explicit company/tenant linkage in Phase 1 schema).
- Required roles:
  - `super_admin`
  - `company_admin`
  - `analyst`

## Phase 2 Gate 2.0 Auth Contract Decisions (`2026-03-05`)
- Auth transport finalized as JWT bearer tokens in the `Authorization` header.
- Phase 2 token model is access-token only (no refresh token lifecycle in this phase).
- Required access-token claims: `sub`, `email`, `role`, `type=access`, `iat`, `exp`.
- Optional configured claims: `iss`, `aud`.
- Route access baseline:
  - public: `POST /api/v1/auth/login`, `GET /health`
  - authenticated (any active role): `/api/v1/auth/me`, `/api/v1/accounts/me` (GET/PATCH), `/api/v1/analytics/*`, `/api/v1/conversations/*`
- Fine-grained role restrictions on analytics/conversations remain deferred to later Milestone 2 phases.

## Phase 3 Gate 3.0 Grading Contract Decisions (`2026-03-09`)
- Provider output contract is a single strict JSON object with field names aligned directly to `conversation_grades`.
- All score, boolean, escalation, and intent fields require companion non-empty English reasoning text.
- `intent_code` is authoritative and `intent_label` must match the canonical label map.
- Parse failures are fail-closed:
  - invalid/malformed/partial model output is rejected
  - no partial grade row is persisted
  - downstream orchestration should treat the result as a controlled parser/provider error
- Provider/runtime retries remain an adapter/orchestration concern, not parser behavior.

## Phase 3.5 Prompt Architecture Revision Direction (`2026-03-09`)
- Move away from the single hardcoded runtime prompt in `app/services/grading_prompt.py`.
- Align runtime prompt structure with `generate_conversation_grades.py`:
  - five markdown prompt files
  - shared `system_prompt.md`
  - prompt-specific `include_system_prompt` behavior
- One customer-day grade executes all five prompt-domain requests asynchronously in parallel, then merges them into one canonical grade result.
- Keep the Phase 3 canonical grading persistence contract (`GradingOutput`) even if legacy markdown prompt wording needs revision.
- Prefer an app-owned versioned prompt-pack directory over working-directory-dependent reads from repo-root markdown files.
- Phase 4 batch execution should wait until this prompt-pack refactor is complete.
- Gate 3.5 contract refinements:
  - prompt-pack root: `app/prompt_assets/grading/<version>/`
  - prompt order remains `ai_performance -> conversation_health -> user_signals -> escalation -> intent`
  - `ai_performance` and `escalation` are the only initial prompt domains that inject `system_prompt.md`
  - the legacy label-based `intent` prompt is retained for parity, but merge logic must normalize `intent_label` to canonical `intent_code` deterministically
  - no DB migration is required for prompt externalization; prompt version remains runtime metadata in Phase 3.5

## Phase 4 Gate 4.0 Batch-Run Decisions (`2026-03-11`)
- Phase 4 operational run-management endpoints are `super_admin`-only in the initial implementation.
- `company_admin` and `analyst` do not receive run-trigger or run-history access in Phase 4 because the current backend has no tenant scoping and run history is global operator data.
- Manual run trigger will return `202 Accepted` after queueing a run and starting execution asynchronously in-process.
- Scheduled execution remains previous-day GST only and defaults to `rerun_existing=false`.
- Manual execution uses:
  - `run_mode=backfill` when `rerun_existing=false`
  - `run_mode=rerun` when `rerun_existing=true`
- Phase 4 run-item vocabulary includes one non-failure skip outcome in addition to the Phase 3 controlled failures:
  - `success`
  - `skipped_existing`
  - `empty_transcript`
  - `provider_error`
  - `parse_error`
- Manual backfill is bounded by configuration only; Phase 4 does not add a separate hardcoded go-live lower-bound date.
- Duplicate-window protection should use both active-run preflight checks and PostgreSQL advisory locking keyed by target date window.

## Phase 5 Graded Metrics API Direction (`2026-03-13`)
- Phase 5 should keep the existing Milestone 1 `/api/v1/analytics/*` endpoints unchanged for legacy raw-chat analytics consumers.
- The new AI Quality Metrics page should consume additive graded-data endpoints under `/api/v1/grading/metrics/*`.
- Metric correctness should come from `conversation_grades`; `grading_runs` should be read only for freshness metadata.
- Default metrics windows should end on the previous GST day, use a 30-day default lookback, and reject wider-than-configured spans.
- Phase 5 access should match the current authenticated analytics baseline (`super_admin`, `company_admin`, and `analyst` allowed) until tenant scoping exists.
- Intent analytics should expose the canonical 16-code taxonomy with category metadata and optional per-code trend filtering.

## Phase 6 Monitoring API Direction (`2026-03-13`)
- Phase 6 should add additive analyst monitoring endpoints under `/api/v1/monitoring/conversations` instead of mutating the existing `/api/v1/conversations/*` contracts.
- The existing `/api/v1/conversations/{conversation_key}/messages` route remains the separate full-conversation view across time; Phase 6 monitoring responses should include `conversation_key` so clients can link to it.
- Monitoring list/detail should be driven by `conversation_grades` joined to raw chats by canonical identity + GST `grade_date`; `grading_runs` should be read only for latest-successful freshness metadata.
- Highlights continue to be computed on read from the current active `monitoring_highlight_config`; historical rows use the current-rules view in Phase 6 because config versioning is still out of scope.
- Phase 6 access should match the existing authenticated analytics/metrics baseline (`super_admin`, `company_admin`, and `analyst` allowed).
- Monitoring list defaults to the previous GST day, remains config-bounded and paginated server-side, and only exposes explicit sort controls for `frustration_score` and `accuracy_score`.
- Monitoring detail should include the same-day transcript, full grade panel, recent grade-history timeline, and canonical intent/highlight metadata.

## Phase 7 Dashboard API Direction (`2026-03-17`)
- Phase 7 should add additive backend-for-frontend endpoints under `/api/v1/grading/dashboard/*` instead of mutating the existing `/api/v1/grading/metrics/*` or `/api/v1/monitoring/conversations/*` contracts.
- The backend contract should follow the three dashboard views in `docs/dashboard_spec.md`:
  - `GET /api/v1/grading/dashboard/agent-pulse`
  - `GET /api/v1/grading/dashboard/correlations`
  - `GET /api/v1/grading/dashboard/daily-timeline`
- Agent Pulse and Correlations should use a bounded GST date window with a shorter dashboard default (`7` days ending on the previous GST day) instead of the broader Phase 5 metrics default.
- Daily Timeline should use a single `target_date` (default previous GST day) plus a bounded `worst_performers_limit`.
- Daily Timeline hour bucketing must use same-day raw-chat timestamps joined through canonical identity + `grade_date`; it should not rely on `conversation_grades.created_at`, which reflects grade-row insertion time rather than analyst-facing conversation activity.
- Story cards and attention signals should be server-generated, deterministic derived insights so the frontend receives ready-to-render severity, metric, and explanation payloads.
- Phase 7 access should match the current authenticated analytics/metrics/monitoring baseline (`super_admin`, `company_admin`, and `analyst` allowed).
- Phase 8 is now reserved for milestone-wide QA/hardening after the new dashboard endpoints are implemented.
- Phase 9 should promote explicit provider families (`openai`, `openrouter`) instead of one generic `openai_compatible` production mode.
- Direct OpenAI should be evaluated inside the backend runtime with the official SDK before any production cutover recommendation is made.
- Provider cutover decisions should be based on a replay corpus that separates transport/client effects from provider/model effects.

## Phase Ordering (High-Level)
- Data contract and migrations should come before auth implementation.
- The data-contract phase should include models needed for auth/accounts as well as Milestone 2 grading/monitoring support.
- Auth/accounts foundation should follow the data-contract phase.
- Dashboard API work should follow the graded metrics and monitoring implementations so it can reuse their stabilized semantics.
- Milestone-wide QA/hardening now follows the dashboard API as Phase 8.
- Provider reliability realignment is now planned as Phase 9 following Phase 8 deployment hardening.

## Conversation/Monitoring Model Direction
- Milestone 2 monitoring should use a `customer-day` (conversation-day) grain, not the Milestone 1 cross-range conversation list behavior.
- A new endpoint surface should be introduced for the customer-day monitoring list and customer-day detail view.
- A separate full conversation view (across time) should still exist as its own endpoint surface.

## Raw Chats Table Policy
- Do not modify the raw chats source table for Milestone 2 linkage.
- Do not add `conversation_grade_id` to raw chat rows.
- Grade/message association should be derived at read/query time using canonical identity + day semantics.

## Grade Identity Model Direction
- `conversation_grades` remains the main grade fact table for Milestone 2.
- The business key should move toward canonical identity + day semantics (instead of relying only on `phone_number`).
- Canonical identity should align with current conversation grouping logic (`phone/email/session` fallback).
- Identity should include explicit type/source semantics (e.g. phone/email/session).

## Intent Classification Storage Direction
- Use `intent_code` + `intent_label` + `intent_reasoning`.
- `intent_code` is the authoritative value for filtering, indexing, and analytics.
- `intent_label` is the display value returned to clients.
- `intent_reasoning` stores AI explanation text.

## Highlights Handling Direction
- Highlights are computed on read in the service layer (not persisted on grade rows initially).
- A shared service function should apply the configured highlight rules and return highlight indicators/codes in responses.
- Highlight thresholds/rules should be configurable (not hardcoded-only).
- A separate database table should store highlight rule configuration to support future admin updates.

## Decisions Deferred to Phase Planning Documents
- Exact schema shape for the highlight-rules configuration table
- Whether highlight configurations are versioned and how active config is selected
- Exact `conversation_grades` migration changes and constraints
- Final API endpoint names/contracts for customer-day monitoring and full conversation views
- Batch run metadata schema and operational controls

## Open Questions to Track (Milestone-Level)
- Phase 2 SRS text says a fixed 16-label intent taxonomy, but the listed labels currently total 15 (needs confirmation in phase planning).
