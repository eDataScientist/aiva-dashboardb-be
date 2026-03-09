# Milestone 2 - Phase 3 Plan: AI Grading Pipeline Core

## Goals
- Build the core customer-day grading pipeline that transforms raw chat messages into one persisted grade per canonical identity per GST day.
- Implement a strict AI output contract covering all Phase 2 score/flag/intent fields with deterministic parse validation.
- Persist grading outputs to `conversation_grades` in a single write path suitable for later batch execution in Phase 4.
- Keep the pipeline internal/service-first in Phase 3 (no new public API surface required).
- Add deterministic tests with provider mocks so grading correctness is verifiable without live model calls.

## Planning Analysis (Required Order)

### 1) Data Models
- `conversation_grades` already includes required Milestone 2 fields for:
  - canonical identity (`identity_type`, `conversation_identity`, `grade_date`)
  - intent (`intent_code`, `intent_label`, `intent_reasoning`)
  - AI Performance, Conversation Health, User Signals, Escalation metrics + reasonings
- Raw chat source remains `Arabia Insurance Chats`; extraction must preserve message order and media/message-type evidence for grading context.
- Phase 3 requires an internal typed grading contract (Pydantic) that mirrors persisted fields and enforces:
  - score ranges (`1..10`)
  - enum domains (`escalation_type`, canonical intent codes)
  - reasoning presence/shape for each scored/boolean field

### 2) Migration
- Phase 3 should be implementation-first and migration-light; only add a migration if write-path constraints are missing for safe persistence.
- A gate validation task must confirm whether canonical write uniqueness can be enforced as:
  - (`identity_type`, `conversation_identity`, `grade_date`) unique key for graded rows
  - while preserving legacy compatibility during transition.
- Any required schema change must be additive-only and downgrade-safe.

### 3) Dependencies
- Upstream complete dependencies:
  - Milestone 2 Phase 1 contract/migrations (`conversation_grades`, intent/highlight constants)
  - Milestone 2 Phase 2 auth foundation (shared guard primitives for future protected grading operations)
  - Async SQLAlchemy and test foundation from Milestone 1.
- Phase 3 should not depend on:
  - scheduler/run-history orchestration (Phase 4)
  - metrics/monitoring endpoint rollout (Phases 5/6).

### 4) Configuration
- Add grading runtime settings with strict validation:
  - provider toggle (`mock`/`openai_compatible` style)
  - model name
  - timeout
  - retry limits
  - optional API key/base URL fields
- Keep provider access abstracted behind a service adapter so tests can fully mock inference behavior.
- Centralize grading prompt/version constants to avoid schema drift between parser, persistence, and future batch execution.

### 5) Endpoints
- No new external API endpoints are required in Phase 3.
- Phase 3 deliverable is internal service orchestration callable from Phase 4 job triggers.
- Optional internal invocation hooks (non-public utility entry points) are acceptable if they do not expose unstable contracts as public API.

## Dependencies
- Phase dependency: `Milestone 2 Phase 2 complete -> Milestone 2 Phase 3`.
- Downstream impact:
  - Phase 4 uses Phase 3 orchestration for daily/manual batch execution and run tracking.
  - Phase 5/6 consume persisted grade data and expect complete field coverage from Phase 3 writes.

## Gate 3.0 - Core Grading Contract and Write Path Readiness

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 3.0.1 | `P2.3.1 - Design - Finalize grading rubric/output contract and parse-failure policy - Gate (Independent)` | Lock required grading output schema (all scores/flags/intent/reasoning fields) plus invalid-output handling policy. | None | `docs/milestone-2/m2-phase-3.md`, `docs/milestone-2/milestone-notes.md` (if decision updates needed) | Review checklist confirms field-level grading contract is explicit and non-ambiguous. |
| 3.0.2 | `P2.3.2 - DB - Validate conversation_grades write constraints and add additive migration if gaps exist - Gate (Dependent)` | Confirm write/upsert readiness for canonical customer-day grading; add additive migration only if needed. | `P2.3.1` | `app/models/conversation_grades.py` (if needed), `alembic/versions/*.py` (conditional) | Alembic upgrade/downgrade smoke if migration added; no destructive schema change. |
| 3.0.3 | `P2.3.3 - Config - Add grading provider/model settings contract and validation - Gate (Dependent)` | Add strict settings for provider/model/timeouts/retries/credentials used by grading adapter. | `P2.3.1` | `app/core/config.py`, `.env.example`, `app/core/__init__.py` | Compile check + config validation checks for missing/invalid grading settings. |
| 3.0.4 | `P2.3.4 - API - Define internal grading schemas and parser error contract - Gate (Dependent)` | Add typed internal request/response parser schemas that map 1:1 to persisted grade fields. | `P2.3.1` | `app/schemas/grading.py` (new), `app/schemas/__init__.py` | Schema import/validation tests for score ranges, enum constraints, and required reasoning fields. |
| 3.0.5 | `P2.3.5 - Service - Scaffold grading module boundaries and shared customer-day selectors - Gate (Dependent)` | Create service modules/interfaces for extraction, prompting, parsing, and persistence with clear call boundaries. | `P2.3.2`, `P2.3.4` | `app/services/grading_*.py` (new modules), `app/services/__init__.py` | Compile/import smoke ensures modules are discoverable without circular imports. |

### P2.3.1 Decision Record - Grading Output Contract and Parse-Failure Policy

#### Decision Summary
- Phase 3 grading uses a single strict JSON object returned by the provider adapter and validated before any persistence occurs.
- The grading payload mirrors `conversation_grades` field names directly for all scored, boolean, enum, and intent outputs.
- Every graded metric, boolean decision, escalation classification, and intent classification requires a non-empty English reasoning string.
- Invalid or partial model output is treated as a controlled parse failure: the pipeline returns an explicit error result and writes nothing to `conversation_grades`.

#### Required Output Shape (Provider -> Parser Contract)
- Root payload type: JSON object only.
- Allowed top-level fields:
  - `relevancy_score`, `relevancy_reasoning`
  - `accuracy_score`, `accuracy_reasoning`
  - `completeness_score`, `completeness_reasoning`
  - `clarity_score`, `clarity_reasoning`
  - `tone_score`, `tone_reasoning`
  - `resolution`, `resolution_reasoning`
  - `repetition_score`, `repetition_reasoning`
  - `loop_detected`, `loop_detected_reasoning`
  - `satisfaction_score`, `satisfaction_reasoning`
  - `frustration_score`, `frustration_reasoning`
  - `user_relevancy`, `user_relevancy_reasoning`
  - `escalation_occurred`, `escalation_occurred_reasoning`
  - `escalation_type`, `escalation_type_reasoning`
  - `intent_code`, `intent_label`, `intent_reasoning`
- No extra fields are accepted by the parser contract.

#### Field Rules
- Score fields (`*_score`) must be integers in the inclusive range `1..10`.
- Boolean fields must be strict JSON booleans (`true` / `false`).
- `escalation_type` must resolve to exactly one canonical value:
  - `Natural`
  - `Failure`
  - `None`
- `intent_code` must be one of the 16 canonical Milestone 2 intent codes.
- `intent_label` must match the canonical label for the supplied `intent_code`.
- Every `*_reasoning` field must be present, string-typed, and non-empty after trimming.
- Reasoning text is expected in English even when the source transcript is Arabic or mixed-language.

#### Parse-Failure Classification
- A provider response is a parse failure if any of the following occur:
  - response is not valid JSON
  - root value is not an object
  - any required field is missing
  - any field has the wrong primitive type
  - any score is out of range
  - any enum/code value is outside the canonical contract
  - `intent_code` and `intent_label` disagree
  - any reasoning field is blank
- Parse failures are classified as controlled pipeline errors, not persistence errors.
- Phase 3 policy is fail-closed:
  - do not coerce missing data
  - do not infer substitute values
  - do not persist a partial grade row

#### Pipeline Outcome Policy
- Successful parse -> validated grade payload continues to persistence.
- Parse failure -> return explicit parser error contract for downstream orchestration/logging and stop before any DB write.
- Provider timeout/transport failure -> return provider error classification and stop before any DB write.
- Retrying malformed output is deferred to provider/orchestration behavior in later tasks; the parser itself remains deterministic and side-effect free.

### P2.3.2 Validation Outcome - Canonical Write Path Readiness

#### Validation Summary
- The pre-existing Milestone 2 schema was not fully write-ready for canonical customer-day grading.
- `conversation_grades.phone_number` remained `NOT NULL`, which blocked persistence for email-only and session-only identities.
- The legacy uniqueness contract (`phone_number`, `grade_date`) was preserved, but it was insufficient for canonical upsert behavior keyed by identity source + identity value + grade date.

#### Gate 3.0 DB Decision
- Keep the legacy `phone_number + grade_date` uniqueness path for backward compatibility.
- Add canonical uniqueness for Phase 3 writes using:
  - `(identity_type, conversation_identity, grade_date)`
  - enforced as a partial unique index when canonical identity fields are present
- Relax `phone_number` to nullable so canonical email/session writes are possible without synthetic phone values.
- Backfill canonical identity fields from `phone_number` for legacy rows before enabling canonical uniqueness enforcement.

#### Migration Scope
- Additive migration required: `alembic/versions/7f0f67f3d1f2_conversation_grades_canonical_write_path.py`
- Model updated:
  - `app/models/conversation_grades.py`
- Migration behavior:
  - backfills missing `identity_type` / `conversation_identity` from existing phone-keyed rows
  - alters `phone_number` to nullable
  - adds partial unique index `uq_conversation_grades_identity_day`
  - downgrade backfills `phone_number` from `conversation_identity` before restoring legacy non-nullability

### Gate 3.0 Acceptance Criteria
- [ ] Grading output contract explicitly covers every persisted score/flag/intent/reasoning field.
- [ ] Any schema delta is additive-only and migration-safe.
- [ ] Grading settings are validated at startup/config load with clear failure messages.
- [ ] Internal grading parser schema is strict enough to reject partial/malformed model outputs.
- [ ] Service module boundaries are established for parallel stream implementation.

## Stream A - Customer-Day Extraction and Transcript Assembly

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.3.6 - Service - Implement customer-day candidate selection and canonical identity grouping - Stream A (Dependent)` | Query grade candidates from chats using GST day + canonical identity rules and skip ungradeable rows. | `P2.3.5` | `app/services/grading_extraction.py` | Service tests with fixture data for phone/email/session fallback and GST-day bucketing. |
| A.2 | `P2.3.7 - Service - Implement transcript assembly/normalization for one customer-day - Stream A (Dependent)` | Build ordered transcript payload including message type, direction, channel, and normalized text/media markers. | `P2.3.6` | `app/services/grading_extraction.py` | Tests verify ordering, null/blank handling, and mixed media message support. |
| A.3 | `P2.3.8 - Test - Add deterministic extraction/normalization fixtures and coverage - Stream A (Dependent)` | Add focused tests and reusable fixtures for candidate selection + transcript assembly edge cases. | `P2.3.7` | `tests/test_grading_extraction.py` (new), `tests/conftest.py` (fixtures if needed) | `pytest tests/test_grading_extraction.py -q`. |

### Stream A Acceptance Criteria
- [x] Candidate selection follows canonical identity contract and GST-day boundaries.
- [x] Transcript assembly preserves chronological order and relevant grading context fields.
- [x] Unusable rows (no canonical identity) are excluded deterministically.
- [x] Stream A tests cover phone/email/session and mixed message-type cases.

### Stream A Execution Notes (Completed `2026-03-09`)
- `P2.3.6` moved to `IN REVIEW`: async candidate selection now executes the GST/canonical identity selector and materializes only valid customer-day candidates.
- `P2.3.7` moved to `IN REVIEW`: transcript assembly now emits normalized structured messages plus deterministic `transcript_text` suitable for downstream prompt building without extra reshaping.
- `P2.3.8` moved to `IN REVIEW`: `tests/test_grading_extraction.py` adds focused coverage for canonical identity fallback, duplicate candidate collapse, grade-date filtering, and transcript normalization; no `tests/conftest.py` changes were required.
- Validation:
  - `python -m py_compile tests/test_grading_extraction.py app/services/grading_extraction.py app/services/__init__.py` passed.
  - sandboxed `pytest tests/test_grading_extraction.py -q` hit the expected Docker npipe permission blocker.
  - unrestricted `pytest tests/test_grading_extraction.py -q` passed (`3 passed`).

## Stream B - Prompting, Provider Adapter, and Parse Validation

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.3.9 - Service - Implement grading prompt builder with rubric and intent taxonomy injection - Stream B (Dependent)` | Build stable prompt payload that includes scoring rubric, escalation rules, and canonical intent taxonomy. | `P2.3.4` | `app/services/grading_prompt.py` (new), `app/core/constants.py` (if prompt constants are centralized) | Prompt unit tests verify required rubric/intent instructions are present. |
| B.2 | `P2.3.10 - Service - Implement AI grader adapter plus strict parse/validation flow - Stream B (Dependent)` | Implement provider adapter and parser that converts model output into validated grading schema or explicit parse failure. | `P2.3.3`, `P2.3.9` | `app/services/grading_provider.py` (new), `app/services/grading_parser.py` (new) | Mocked provider tests for valid output, malformed output, timeout, and retry behavior. |
| B.3 | `P2.3.11 - Test - Add prompt/parser contract tests with mocked provider responses - Stream B (Dependent)` | Add deterministic tests for parser correctness, enum/score validation, and failure-path error mapping. | `P2.3.10` | `tests/test_grading_parser.py` (new) | `pytest tests/test_grading_parser.py -q`. |

### Stream B Acceptance Criteria
- [ ] Prompt contract includes all required dimensions, definitions, and output format guidance.
- [ ] Provider adapter is isolated behind an interface that supports full mocking in tests.
- [ ] Parser rejects malformed/partial outputs with explicit error classification.
- [ ] Stream B tests cover success and controlled failure paths.

## Stream C - Persistence and Core Orchestration

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.3.12 - Service - Implement conversation_grades upsert persistence for one customer-day - Stream C (Dependent)` | Persist full grading result (all fields) in one write operation, preserving canonical identity and grade date semantics. | `P2.3.2`, `P2.3.4` | `app/services/grading_persistence.py` (new), `app/models/conversation_grades.py` (if helper updates are needed) | Persistence tests validate insert/update behavior and field completeness. |
| C.2 | `P2.3.13 - Service - Implement grade_customer_day orchestration (extract -> grade -> persist) - Stream C (Dependent)` | Compose extraction, prompting/provider, parser, and persistence into a single orchestration path for one customer-day unit. | `P2.3.8`, `P2.3.11`, `P2.3.12` | `app/services/grading_pipeline.py` (new), `app/services/__init__.py` | Orchestration tests for happy path and controlled parse/provider failures. |
| C.3 | `P2.3.14 - Test - Add grading pipeline service tests for idempotent reruns and partial-failure behavior - Stream C (Dependent)` | Verify repeated grading overwrites safely and failure paths avoid partially-written grade records. | `P2.3.13` | `tests/test_grading_pipeline.py` (new) | `pytest tests/test_grading_pipeline.py -q`. |

### Stream C Acceptance Criteria
- [x] Persistence writes all required grade fields in one transaction scope.
- [x] Pipeline orchestration is deterministic for the same input fixtures and mocked model output.
- [x] Rerun behavior is safe (same customer-day can be regraded without duplicates).
- [x] Stream C tests cover transaction safety and failure handling.

### Stream C Execution Notes (Completed `2026-03-09`)
- `P2.3.12` moved to `IN REVIEW`: `app/services/grading_persistence.py` now upserts one canonical customer-day grade row, while phone-keyed reruns safely reuse legacy `phone_number + grade_date` rows instead of duplicating them.
- `P2.3.13` moved to `IN REVIEW`: `app/services/grading_pipeline.py` now assembles the transcript, builds the prompt, executes the provider, parses the result, and persists the validated output through a single internal orchestration boundary.
- `P2.3.14` moved to `IN REVIEW`: `tests/test_grading_pipeline.py` now covers direct persistence behavior, end-to-end pipeline success, provider failure, parse failure, and rerun overwrite safety.
- Validation:
  - `python -m compileall app/services/grading_persistence.py app/services/grading_pipeline.py app/services/__init__.py tests/test_grading_pipeline.py` passed.
  - `pytest tests/test_grading_pipeline.py -q` passed (`6 passed`).

### Stream C Review Fix Notes (`2026-03-09`)
- `P2.3.12` review approved with no required fixes and moved to `DONE`.
- `P2.3.13` review fix applied: `grade_customer_day()` now returns explicit success/failure result objects instead of surfacing provider/parser failures as exceptions, and it classifies controlled failures as `EMPTY_TRANSCRIPT`, `PROVIDER_ERROR`, or `PARSE_ERROR`.
- `P2.3.14` review fix applied: failure-path tests now assert the explicit orchestration result contract, and empty-transcript coverage verifies the pipeline skips provider/persistence work when no transcript evidence exists.
- Revalidation:
  - `python -m compileall app/services/grading_pipeline.py app/services/__init__.py tests/test_grading_pipeline.py` passed.
  - `pytest tests/test_grading_pipeline.py -q` passed (`7 passed`).

### Stream C Rereview Outcome (`2026-03-09`)
- `P2.3.12` (`EDA-95`) approved and moved to `DONE`.
- `P2.3.13` (`EDA-96`) approved and moved to `DONE` after the explicit failure-result contract fix:
  - success and controlled failure paths now share one stable orchestration boundary for downstream Phase 4 consumers
  - empty transcripts now short-circuit before provider execution and persistence
- `P2.3.14` (`EDA-97`) approved and moved to `DONE`:
  - tests now assert the explicit failure-result model for provider/parser failures
  - empty-transcript coverage now guards against no-evidence grading writes
- Rereview validation:
  - `python -m compileall app/services/grading_pipeline.py app/services/__init__.py tests/test_grading_pipeline.py` passed.
  - `pytest tests/test_grading_pipeline.py -q` passed (`7 passed`).

## Stream D - Phase Validation and Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.3.15 - QA - Run compile and targeted pytest verification for grading pipeline scope - Stream D (Dependent)` | Execute compile and targeted grading test suite verification for Phase 3 modules. | `P2.3.14` | No mandatory code files; QA notes in task records | `python -m compileall app tests` and targeted grading `pytest` suites. |
| D.2 | `P2.3.16 - Docs - Update task/progress docs with Phase 3 execution notes and Phase 4 handoff risks - Stream D (Dependent)` | Sync docs after execution/review and capture residual risks for Phase 4 batch orchestration. | `P2.3.15` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-3.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Acceptance Criteria
- [x] Compile checks pass for modified Python modules.
- [x] Targeted grading extraction/parser/pipeline tests pass (or blockers are explicitly documented).
- [x] Docs are synchronized with execution/review outcomes and handoff notes.

### Stream D Execution Notes (Completed `2026-03-09`)
- `P2.3.15` moved to `IN REVIEW`: Phase 3 compile verification passed and the targeted grading suite was rerun unrestricted after the expected sandbox Docker/Testcontainers blocker.
- `P2.3.16` moved to `IN REVIEW`: `docs/tasks.md`, `docs/project-progress.md`, and `docs/milestone-2/m2-phase-3.md` were synchronized with Stream D execution status and Phase 4 handoff notes.
- Validation:
  - `python -m compileall app tests` passed.
  - sandboxed `pytest tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_extraction.py tests/test_grading_prompt.py tests/test_grading_parser.py tests/test_grading_pipeline.py -q` partially passed (`21 passed`) before extraction/pipeline suites hit the expected Docker npipe permission blocker (`CreateFile Access is denied`).
  - unrestricted `pytest tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_extraction.py tests/test_grading_prompt.py tests/test_grading_parser.py tests/test_grading_pipeline.py -q` passed (`31 passed`).

### Residual Risks / Handoff Notes (`2026-03-09`)
- Environment/runtime: extraction and pipeline tests still require unrestricted Docker/Testcontainers access in this environment.
- Provider/runtime: `GRADING_PROVIDER=mock` remains valid for deterministic local/test execution, but Phase 4 non-test batch runs need explicit external-provider configuration before live grading.
- Orchestration contract: Phase 4 batch/run-history work must consume the in-band `EMPTY_TRANSCRIPT`, `PROVIDER_ERROR`, and `PARSE_ERROR` result model from `grade_customer_day()` instead of assuming exception-only failures.

### Stream D Closure Note (`2026-03-09`)
- `P2.3.15` (`EDA-98`) was moved to `DONE` without separate review because it was validation-only and modified no repository files.
- `P2.3.16` (`EDA-99`) was moved to `DONE` without separate review because it modified documentation only and no code files.

## Suggested Files by Concern
- Config and constants:
  - `app/core/config.py`
  - `app/core/constants.py`
  - `.env.example`
- Internal schemas:
  - `app/schemas/grading.py` (new)
  - `app/schemas/__init__.py`
- Grading services:
  - `app/services/grading_extraction.py` (new)
  - `app/services/grading_prompt.py` (new)
  - `app/services/grading_provider.py` (new)
  - `app/services/grading_parser.py` (new)
  - `app/services/grading_persistence.py` (new)
  - `app/services/grading_pipeline.py` (new)
  - `app/services/__init__.py`
- Models/migrations (conditional):
  - `app/models/conversation_grades.py`
  - `alembic/versions/*.py`
- Tests:
  - `tests/test_grading_extraction.py` (new)
  - `tests/test_grading_parser.py` (new)
  - `tests/test_grading_pipeline.py` (new)
  - `tests/conftest.py` (fixture extensions if required)

## Component Dependency Summary
- Gate 3.0 defines grading contracts and write-path readiness used by all streams.
- Stream A (extraction) and Stream B (prompt/provider/parser) can run in parallel after Gate 3.0.
- Stream C depends on outputs from both Stream A and Stream B plus persistence readiness.
- Stream D validates and documents Phase 3 outcomes after Stream C.

## Parallelization Map

```text
Gate 3.0 (P2.3.1 - P2.3.5 Core grading contract + readiness) --------+
                                                                      |
  |- Stream A (customer-day extraction + transcript assembly) ------> |
  |- Stream B (prompt/provider/parser) ------------------------------> |  (parallel after Gate)
                                                                      |
  |- Stream C (persist + orchestration) ----------------------------> |  (after A/B)
                                                                      |
  |- Stream D (compile/tests/docs handoff) -------------------------> |  (after C)
                                                                      v
                  Phase 3 Complete (AI Grading Pipeline Core)
```

## Definition of Done (Phase 3)
- [ ] Core grading service can build customer-day transcript input and produce validated grading output.
- [ ] Full grade payload persists to `conversation_grades` with canonical identity + grade-date semantics.
- [ ] Reruns for the same customer-day are idempotent/overwrite-safe (no duplicate-grade behavior).
- [ ] Parse/provider failures are handled explicitly without partial grade writes.
- [ ] Deterministic mocked tests exist for extraction, parser, and orchestration paths.
- [ ] No lint/syntax errors in modified Python modules.

## Test Scenarios (Phase 3 Validation)

### Happy Path
- Customer-day candidate extraction returns expected grouped identities for a GST day range.
- Transcript assembly preserves message chronology and required context fields.
- Mocked grading provider returns valid payload; parser validates and persistence writes all fields.
- Regrading the same customer-day updates existing grade row deterministically.

### Edge Cases
- Rows without canonical identity are skipped safely.
- Mixed-language transcripts and mixed media message types do not break transcript assembly.
- Provider timeout or malformed output returns controlled pipeline error and avoids partial DB writes.
- Invalid score or enum value from model output is rejected by parser validation.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- Phase 3 remains internal-service scope with no public grading endpoint.
- Provider interaction is abstracted and fully mockable; live provider integration details can remain minimal in this phase.
- Prompt output format is strict JSON (or equivalent schema-constrained payload) to keep parse behavior deterministic.
- `conversation_grades` currently has sufficient columns for Phase 3 writes; only constraints/indexes may need additive adjustment.

### Open Questions
- Final default provider mode for non-test environments (`mock` fallback vs mandatory external provider credentials).
- Whether strict DB-level uniqueness on canonical (`identity_type`, `conversation_identity`, `grade_date`) should be enforced in Phase 3 or deferred to Phase 4 run-management work.

## Estimated Duration (Units)
- Gate 3.0 (`P2.3.1` - `P2.3.5`): `2.25`
- Stream A (`P2.3.6` - `P2.3.8`): `1.75`
- Stream B (`P2.3.9` - `P2.3.11`): `1.75`
- Stream C (`P2.3.12` - `P2.3.14`): `1.75`
- Stream D (`P2.3.15` - `P2.3.16`): `0.75`
- Sequential total: `8.25`
- Parallelized total after Gate (A/B concurrent, then C, then D): `~6.0 - 6.5`

## Done Condition for Phase 3 Planning
Phase 3 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-3.md`).
- Gate/stream tasks are atomic, dependency-linked, and execution-ready.
- `docs/tasks.md` checklist includes Phase 3 task entries aligned to this plan.
- Kanban task creation remains deferred unless explicitly requested.
