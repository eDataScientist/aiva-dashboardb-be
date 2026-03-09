# Milestone 2 SRS: AI Grading, Monitoring, and Access Foundations

## Purpose
Milestone 2 expands the backend from Milestone 1 analytics into a graded AI monitoring platform by introducing:
- A structured AI-as-a-Judge grading pipeline (customer-day grading)
- AI Quality Metrics APIs backed by persisted grade data
- A conversations monitoring API overhaul (customer-day monitoring + day detail)
- Simple password authentication and account profiles

This document is intentionally high-level. Detailed execution planning will be split into phase documents (starting with `docs/milestone-2/m2-phase-1.md`).

## Goals
- Introduce a reliable backend data contract for graded conversation metrics and intent classification.
- Add a simple authentication layer and account profile support for protected Milestone 2 features.
- Build a grading pipeline that evaluates customer-day conversations and persists structured grades.
- Deliver new APIs for AI Quality Metrics and customer-day monitoring workflows.
- Keep legacy raw chat data stable and non-destructive while adding derived grading capabilities.

## Out of Scope
- Real-time/live grading
- Manual analyst grade overrides
- External CRM/ticketing integrations
- Advanced auth features (RBAC, SSO, MFA)
- Mobile-specific API variants
- Full observability stack beyond milestone operational needs

## Phase Plan (Brief)

## Phase 1 - Data Contract and Migrations (Milestone 2 + Auth Models)
Objective: Finalize schema contracts and migrations needed by all Milestone 2 features, including auth/account models.

Subtasks (brief):
- Refine `conversation_grades` for Milestone 2 (canonical identity + intent code support).
- Add support/config tables needed downstream (for example highlight rules configuration).
- Add auth/account data models and migration(s).
- Add indexes/constraints/shared enums/constants for grading and monitoring.

## Phase 2 - Auth and Accounts Foundation
Objective: Add simple password auth and account profile capabilities used to protect Milestone 2 features.

Subtasks (brief):
- Implement simple password-based authentication flow.
- Add account profile endpoints and persistence.
- Add auth dependencies/guards for protected route groups.
- Establish baseline access patterns for Milestone 2 endpoints.

## Phase 3 - AI Grading Pipeline Core
Objective: Build core grading logic that produces one structured grade per customer-day.

Subtasks (brief):
- Build customer-day transcript extraction/aggregation.
- Implement AI grading prompt/parse/validate/persist flow.
- Persist grade metrics, flags, and intent classification in one pass.
- Validate core grading correctness with deterministic fixtures/mocks.

## Phase 3.5 - Prompt Externalization and Legacy Prompt Alignment
Objective: Move runtime grading away from the single hardcoded prompt and onto a versioned markdown prompt pack aligned to the legacy generator structure.

Subtasks (brief):
- Externalize grading prompts into versioned markdown assets.
- Reintroduce the legacy five-prompt decomposition (`ai_performance`, `conversation_health`, `user_signals`, `escalation`, `intent`) in runtime services.
- Add prompt-pack loading/version validation and deterministic merge back into canonical grading output.
- Verify prompt-driven grading behavior before operational batch execution begins.

## Phase 4 - Batch Execution and Run Management
Objective: Operationalize grading with daily execution, manual triggers, and run tracking.

Subtasks (brief):
- Add daily grading job orchestration.
- Add manual trigger/backfill entry points (scope may be limited).
- Add idempotency/re-run safety.
- Add run status/history/error tracking.

## Phase 5 - AI Quality Metrics API
Objective: Deliver backend APIs for the new AI Quality Metrics page using graded data.

Subtasks (brief):
- Build aggregate/trend endpoints backed by `conversation_grades`.
- Add date-filtered metric trend APIs across grading dimensions.
- Add intent distribution/trend APIs using canonical `intent_code`.
- Replace dependence on the Milestone 1 single AI Quality Index model for new consumers.

## Phase 6 - Conversations Monitoring API Overhaul
Objective: Deliver a new analyst monitoring surface centered on customer-day records and graded outcomes.

Subtasks (brief):
- Add customer-day monitoring list endpoint (server-side filter/sort/highlights).
- Add conversation-day detail endpoint (grade panel + day transcript).
- Preserve a separate full conversation view endpoint surface (across time).
- Compute highlights on read in the service layer using configurable rules.

## Phase 7 - Testing, QA, and Hardening
Objective: Validate Milestone 2 end-to-end and leave the project in a stable, reviewable state.

Subtasks (brief):
- Add/expand tests for auth, profiles, grading, metrics, and monitoring endpoints.
- Add fixture-based parser validation and integration coverage.
- Run milestone QA verification (migrations, runtime checks, API behavior).
- Finalize handoff-ready documentation and checklist status.

## Phase Dependencies
- `Phase 1 -> Phase 2 -> Phase 3`
- `Phase 3.5` depends on `Phase 3`
- `Phase 4` depends on `Phase 3.5`
- `Phase 5` depends on `Phase 3` (and may consume execution outputs standardized in `Phase 4`)
- `Phase 6` depends on `Phase 2` and `Phase 3`
- `Phase 7` closes the milestone after implementation phases complete

Exact gate/stream parallelism will be defined in each phase document.

## Milestone Deliverables
- Updated schema/migrations for Milestone 2 grading and auth/account models
- Simple password auth layer and account profile APIs
- AI grading pipeline core and batch execution flow
- Versioned grading prompt pack aligned to the legacy markdown prompt workflow
- AI Quality Metrics API endpoints (graded-data based)
- Customer-day conversations monitoring API endpoints
- Expanded automated test coverage for new milestone features

## Success Criteria
- Milestone 2 schema migrations apply cleanly without destructive changes to raw chat data.
- Protected endpoints authenticate successfully with the selected simple auth flow.
- Grading pipeline persists valid customer-day grades with intent classification.
- Batch runs can be triggered and tracked safely (including repeat-run protections).
- AI Quality Metrics and monitoring endpoints return stable, documented, filterable responses.
- Highlights are computed consistently on read using configurable rules.
- Milestone 2 test and QA checks pass for modified areas.
