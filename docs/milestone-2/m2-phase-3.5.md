# Milestone 2 - Phase 3.5 Plan: Prompt Externalization and Legacy Multi-Prompt Alignment

## Goals
- Replace the single hardcoded grading prompt with a versioned, file-based prompt pack aligned to the legacy `generate_conversation_grades.py` workflow.
- Split grading into the same five logical prompt domains used by the legacy generator:
  - `ai_performance`
  - `conversation_health`
  - `user_signals`
  - `escalation`
  - `intent`
- One customer-day grade executes as five async prompt calls in parallel, then merges the five partial outputs into one canonical grading result.
- Preserve the Phase 3 strict parsing and canonical `GradingOutput` contract while moving prompt content out of Python source.
- Make prompt revisions operationally safe by versioning prompt assets and validating required prompt files/placeholders at startup/test time.
- Block Phase 4 batch/run-management execution until prompt architecture is stable and reviewable.

## Planning Analysis (Required Order)

### 1) Data Models
- No database contract change is expected for this phase.
- `conversation_grades` remains the single canonical persistence target.
- Phase 3.5 introduces internal prompt-domain contracts rather than new tables:
  - prompt pack manifest/spec:
    - `prompt_key`
    - `template_file`
    - `output_fields`
    - `include_system_prompt`
  - versioned prompt asset set:
    - `system_prompt.md`
    - `ai_performance_judge.md`
    - `conversation_health.md`
    - `user-signals.md`
    - `escalation.md`
    - `intent.md`
  - partial prompt output models or equivalent parser contracts for each of the five prompt domains
- Final runtime output must still merge into one canonical `GradingOutput`.
- Intent handling needs explicit planning because the legacy script returns `intent_label` + `intent_reasoning`, while the current runtime contract persists canonical `intent_code` + `intent_label` + `intent_reasoning`.
- Planning baseline:
  - keep the externalized multi-prompt structure modeled on the legacy script
  - keep the runtime persistence contract modeled on Phase 3
  - bridge any mismatch with a deterministic normalization/merge step rather than weakening the Phase 3 schema contract

### 2) Migration
- Default path: no migration is expected.
- This phase is a prompt/runtime refactor and should not alter raw chats, `conversation_grades`, or auth tables.
- A gate task should still explicitly validate that no additive schema change is needed.
- If prompt-version metadata ever needs DB persistence, that should be deferred unless proven necessary by execution requirements.

### 3) Dependencies
- Upstream dependencies satisfied:
  - Milestone 2 Phase 3 extraction, provider adapter, strict parser, and orchestration
  - existing markdown prompt assets used by `generate_conversation_grades.py`
- Phase 3.5 must bridge the gap between:
  - legacy prompt asset structure in the repo root
  - current inline prompt builder in `app/services/grading_prompt.py`
- Phase 4 should not begin execution until Phase 3.5 is complete because:
  - batch execution amplifies prompt defects operationally
  - prompt versioning and prompt-pack validation need to be stable first
- Existing Phase 3 controlled result handling (`EMPTY_TRANSCRIPT`, `PROVIDER_ERROR`, `PARSE_ERROR`) remains authoritative and must survive the refactor unchanged at the orchestration boundary.

### 4) Configuration
- Add explicit prompt-pack configuration and validation for:
  - active prompt pack version/name
  - optional prompt asset root override for local development/testing
  - strict startup validation for required prompt files and placeholders
- Planning baseline for asset location:
  - move or copy grading prompt assets into an app-owned versioned directory, for example:
    - `app/prompt_assets/grading/<version>/...`
- Avoid working-directory-dependent file loading from the repo root in runtime code.
- Prompt version metadata returned by the builder should reflect the active prompt pack version, not a hardcoded inline constant detached from asset content.

### 5) Endpoints
- No new external API endpoints are required in this phase.
- Phase 3.5 is internal-service scope only.
- Acceptable API impact:
  - none, or
  - internal schema modules used by services/tests only
- Phase 4 manual trigger/history endpoints must consume the post-refactor prompt pipeline rather than the current inline-prompt implementation.

## Dependencies
- Phase dependency: `Milestone 2 Phase 3 complete -> Milestone 2 Phase 3.5 -> Milestone 2 Phase 4`
- Downstream impact:
  - Phase 4 batch execution depends on a stable versioned prompt pack and multi-prompt orchestration path
  - Phase 5 and Phase 6 depend indirectly on Phase 3.5 because prompt changes affect grade quality and downstream metrics/monitoring correctness

## Prompt Architecture Revision Scope (Planning Baseline)

### Legacy Behavior to Preserve
- Five distinct markdown prompts, each with a bounded output surface.
- Selective inclusion of `system_prompt.md` for prompt domains that require it.
- External prompt files editable without changing Python logic.
- Stable prompt ordering and prompt-specific output-field ownership.

### Current Runtime Behavior to Replace
- One large hardcoded system prompt embedded in `app/services/grading_prompt.py`.
- One provider call producing the full `GradingOutput` payload at once.
- Prompt versioning disconnected from on-disk prompt assets.

### Target Runtime Direction
- File-based prompt pack loaded by version.
- Exactly five prompt-domain requests execute asynchronously in parallel for one customer-day candidate.
- Per-domain prompt generation aligned to the legacy script’s decomposition.
- Partial outputs parsed/validated per prompt domain, then merged into one canonical `GradingOutput`.
- Deterministic normalization step for canonical intent storage and any legacy prompt-field mismatches.

## Gate 3.5 - Prompt Pack Contract and Runtime Boundaries

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 3.5.1 | `P2.35.1 - Design - Finalize prompt-pack contract, legacy parity scope, and merge strategy - Gate (Independent)` | Lock the file-based prompt-pack model, the five prompt domains, system-prompt injection rules, and canonical merge contract. | None | `docs/milestone-2/m2-phase-3.5.md`, `docs/milestone-2/milestone-notes.md` | Review checklist confirms legacy parity scope and canonical merge rules are explicit. |
| 3.5.2 | `P2.35.2 - DB - Validate that no migration is required for prompt externalization scope - Gate (Dependent)` | Confirm prompt refactor requires no schema change and document any bounded deferral if a metadata field is considered. | `P2.35.1` | No expected code changes; conditional notes in phase docs only | Review validation confirms `conversation_grades` and existing run-planning schema assumptions remain unchanged. |
| 3.5.3 | `P2.35.3 - Config - Add prompt-pack settings and validation contract - Gate (Dependent)` | Add settings for active prompt-pack version/asset root and fail-fast validation for missing assets/placeholders. | `P2.35.1` | `app/core/config.py`, `app/core/__init__.py`, `.env.example` | Compile check and config validation tests for missing/invalid prompt-pack settings. |
| 3.5.4 | `P2.35.4 - API - Define internal prompt-spec and partial-output schemas - Gate (Dependent)` | Add typed internal models for prompt specs and per-domain parsed output before final merge to `GradingOutput`. | `P2.35.1` | `app/schemas/grading_prompts.py` (new), `app/schemas/__init__.py`, `app/schemas/grading.py` (if needed) | Schema import/validation tests for partial outputs and merge prerequisites. |
| 3.5.5 | `P2.35.5 - Service - Scaffold prompt-pack loader and multi-prompt orchestration module boundaries - Gate (Dependent)` | Establish loader/builder/merger module boundaries without circular imports or working-directory coupling. | `P2.35.3`, `P2.35.4` | `app/services/grading_prompt_assets.py` (new), `app/services/grading_prompt.py`, `app/services/__init__.py` | Compile/import smoke check for new prompt-pack boundaries. |

### Gate 3.5 Acceptance Criteria
- [x] Prompt-pack structure, system-prompt inclusion rules, and merge strategy are explicit and versioned.
- [x] It is documented that no DB migration is required unless a later execution need proves otherwise.
- [x] Prompt-pack settings are validated at startup/config load.
- [x] Internal prompt-domain schema contracts exist for multi-prompt parsing and merge.
- [x] Service boundaries exist for file loading, prompt building, and merge orchestration.

### P2.35.1 Decision Record - Prompt-Pack Contract, Legacy Parity Scope, and Merge Strategy

#### Decision Summary
- The active runtime prompt pack is versioned by `grading_prompt_version` and loaded from an app-owned directory:
  - `app/prompt_assets/grading/<version>/`
- Phase 3.5 preserves the legacy five-domain grading flow and prompt order exactly:
  1. `ai_performance`
  2. `conversation_health`
  3. `user_signals`
  4. `escalation`
  5. `intent`
- Prompt-domain execution will remain bounded:
  - each domain owns only its declared output fields
  - domain outputs merge into one canonical Phase 3 `GradingOutput`
  - any missing/invalid domain output fails the whole grade before persistence

#### Prompt-Pack File Contract
- Required files for prompt pack version `<version>`:
  - `system_prompt.md`
  - `ai_performance_judge.md`
  - `conversation_health.md`
  - `user-signals.md`
  - `escalation.md`
  - `intent.md`
- File names remain aligned to the legacy generator to minimize operational drift during the refactor.
- Runtime code must not depend on repo-root prompt files or the current working directory.

#### Prompt-Domain Contract

| prompt_key | template_file | output_fields | include_system_prompt |
|---|---|---|---|
| `ai_performance` | `ai_performance_judge.md` | `relevancy_*`, `accuracy_*`, `completeness_*`, `clarity_*`, `tone_*` | `true` |
| `conversation_health` | `conversation_health.md` | `resolution*`, `repetition_*`, `loop_detected*` | `false` |
| `user_signals` | `user-signals.md` | `satisfaction_*`, `frustration_*`, `user_relevancy*` | `false` |
| `escalation` | `escalation.md` | `escalation_occurred*`, `escalation_type*` | `true` |
| `intent` | `intent.md` | `intent_label`, `intent_reasoning` | `false` |

#### Placeholder and Validation Contract
- Every prompt-domain markdown file must contain `{{conversation}}`.
- `system_prompt.md` is raw content only and is injected by runtime code.
- A prompt-domain template with `include_system_prompt = true` must contain `{{system_prompt}}`.
- A prompt-domain template with `include_system_prompt = false` must not require `{{system_prompt}}`.
- Unknown `{{placeholder}}` tokens are rejected during prompt-pack validation.

#### Legacy Parity Scope
- Legacy parity means preserving:
  - the five prompt domains
  - the prompt ordering
  - the prompt-file names
  - the selective `system_prompt.md` inclusion behavior
- Legacy parity does not require preserving legacy weaknesses that conflict with the Phase 3 canonical write contract.
- Prompt wording may be revised in the app-owned pack where needed to support strict parsing and canonical intent persistence.

#### Canonical Merge Strategy
- Merge order follows prompt order only for deterministic logging/debuggability; field ownership is non-overlapping.
- Each prompt domain contributes only its declared output fields.
- The merged payload must populate every field required by Phase 3 `GradingOutput`.
- Final merged output is validated again as canonical `GradingOutput` before persistence.
- One malformed/missing prompt-domain result fails the merged output and maps to the controlled parse-failure path.

#### Intent Normalization Rule
- The legacy `intent.md` prompt remains label-based in Phase 3.5 gate scope for parity with `generate_conversation_grades.py`.
- Canonical runtime storage still requires `intent_code`, `intent_label`, and `intent_reasoning`.
- Merge behavior:
  - accept `intent_label` + `intent_reasoning` from the intent prompt
  - normalize `intent_label` to canonical `intent_code` using a deterministic inverse label map
  - reject the merge if the returned label is blank or outside the canonical label set
- This keeps prompt structure aligned with the legacy script without weakening Phase 3 persistence rules.

### P2.35.2 Validation Outcome - No Migration Required

#### Validation Summary
- Phase 3.5 is an internal prompt/runtime refactor only.
- No new persisted grading fields are required to externalize prompt assets or introduce prompt-domain parsing/merge.
- Existing canonical storage remains sufficient:
  - `conversation_grades` continues to store the final merged grading result
  - Phase 4 run-management planning can continue to treat prompt version as runtime metadata unless operational evidence requires persistence later

#### Gate 3.5 DB Decision
- No Alembic migration is required for Gate 3.5 or the broader Phase 3.5 prompt externalization scope.
- Prompt-pack version, asset root, and prompt-domain execution metadata remain runtime-only in Phase 3.5.
- If future operators require persisted prompt-version lineage on grade rows or run-history tables, that change is deferred to a later additive migration and is explicitly out of scope for this phase.

#### Bounded Deferrals
- Persisting prompt-pack version on `conversation_grades`: deferred.
- Persisting per-domain raw prompt output or provider payloads: deferred.
- Any schema work related to operational run history remains a Phase 4 concern, not a Phase 3.5 prerequisite.

### Gate 3.5 Execution Notes (Completed `2026-03-09`; tasks moved to `IN REVIEW`)
- `P2.35.1` completed:
  - prompt-pack directory/version contract, placeholder rules, legacy parity scope, and label-to-code intent normalization were finalized in this phase doc
  - milestone planning notes were synchronized in `docs/milestone-2/milestone-notes.md`
- `P2.35.2` completed:
  - no migration requirement was validated and documented
  - prompt-pack metadata persistence remains explicitly deferred beyond Phase 3.5
- `P2.35.3` completed:
  - prompt-pack settings and startup validation added to `app/core/config.py`
  - prompt-pack constants/export surface added under `app/core/constants.py` and `app/core/__init__.py`
  - `.env.example` now includes `GRADING_PROMPT_ASSETS_ROOT`
  - baseline versioned prompt-pack scaffold added under `app/prompt_assets/grading/v1/`
- `P2.35.4` completed:
  - internal prompt-pack manifest/spec schemas and per-domain partial-output schemas added in `app/schemas/grading_prompts.py`
  - schema exports updated in `app/schemas/__init__.py`
- `P2.35.5` completed:
  - prompt-pack manifest/loader scaffolding added in `app/services/grading_prompt_assets.py`
  - prompt execution-plan scaffolding added in `app/services/grading_prompt.py`
  - provider transport now supports prompt bundles with or without a system message
  - service exports updated in `app/services/__init__.py`
- Validation:
  - `python -m compileall app/core app/schemas app/services tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_prompt.py` passed
  - `pytest tests/test_grading_config.py tests/test_grading_schemas.py tests/test_grading_prompt.py tests/test_grading_parser.py -q` passed (`26 passed`)
  - environment note: pytest emitted non-blocking warnings about this machine not being able to write `.pytest_cache`

### Gate 3.5 Review Outcome (`2026-03-09`)
- Approved and moved to `DONE`:
  - `P2.35.1`
  - `P2.35.2`
- Kept in `IN REVIEW` for fixes:
  - `P2.35.3`
  - `P2.35.4`
  - `P2.35.5`
- Review findings:
  - `build_grading_prompt()` still reports `GRADING_DEFAULT_PROMPT_VERSION` instead of the active prompt-pack version, so prompt metadata can drift from configuration
  - `PromptPackManifest` validation currently accepts incomplete prompt-domain sets even though Gate 3.5 fixed the runtime contract at exactly five domains
  - the current prompt scaffolding duplicates `system_prompt.md` for `ai_performance` and `escalation` by rendering it into the user prompt and also sending it as a provider system message

### Gate 3.5 Rereview Outcome (`2026-03-10`)
- Approved and moved to `DONE`:
  - `P2.35.3`
  - `P2.35.4`
  - `P2.35.5`
- Rereview outcomes:
  - `build_grading_prompt()` now sources `prompt_version` from the active settings contract
  - `PromptPackManifest` now requires the full fixed five-domain sequence, and schema tests reject incomplete manifests
  - prompt execution plans now inject `system_prompt.md` through one channel only, and prompt tests confirm the previous duplication is gone

## Stream A - Prompt Assets and File Loader

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.35.6 - Service - Externalize grading prompts into versioned markdown prompt-pack assets - Stream A (Dependent)` | Move/copy the legacy grading markdown prompts into an app-owned versioned asset pack used by runtime code. | `P2.35.5` | `app/prompt_assets/grading/<version>/*.md` (new), legacy root files only if redirects/deprecation notes are needed | Asset review confirms all required prompt files exist and are version-scoped. |
| A.2 | `P2.35.7 - Service - Implement prompt-pack file loader with shared system-prompt injection rules - Stream A (Dependent)` | Load prompt assets by version, validate placeholders, and expose prompt specs for builder/orchestrator use. | `P2.35.6` | `app/services/grading_prompt_assets.py`, `app/services/grading_prompt.py` | Loader tests for missing files, bad placeholders, and correct system-prompt inclusion flags. |
| A.3 | `P2.35.8 - Test - Add prompt-pack loader and asset integrity tests - Stream A (Dependent)` | Add deterministic coverage for asset discovery, placeholder validation, and version selection. | `P2.35.7` | `tests/test_grading_prompt_assets.py` (new) | `pytest tests/test_grading_prompt_assets.py -q`. |

### Stream A Acceptance Criteria
- [ ] Runtime prompt assets live in a versioned app-owned directory, not a hardcoded inline string.
- [ ] Loader resolves the active prompt pack deterministically without depending on the current working directory.
- [ ] Required markdown files and placeholders are validated before execution.
- [ ] Stream A tests cover asset integrity and failure modes.

## Stream B - Multi-Prompt Build, Parse, and Canonical Merge

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.35.9 - Service - Implement per-domain prompt bundle generation aligned to legacy 5-prompt flow - Stream B (Dependent)` | Build prompt bundles from the file-based pack for the five prompt domains with prompt-specific metadata and prompt order. | `P2.35.7` | `app/services/grading_prompt.py`, `app/schemas/grading_prompts.py` | Unit tests verify prompt order, file rendering, and transcript/system-prompt insertion. |
| B.2 | `P2.35.10 - Service - Implement partial-result parsing and canonical GradingOutput merge - Stream B (Dependent)` | Parse each prompt’s bounded output and merge the five results into one strict canonical `GradingOutput`. | `P2.35.4`, `P2.35.9` | `app/services/grading_parser.py`, `app/schemas/grading.py`, `app/schemas/grading_prompts.py` | Tests for per-domain validation, missing prompt fields, and canonical intent normalization. |
| B.3 | `P2.35.11 - Test - Add deterministic multi-prompt parse and merge contract tests - Stream B (Dependent)` | Add coverage for successful five-prompt merge and controlled failure behavior when one prompt returns malformed output. | `P2.35.10` | `tests/test_grading_parser.py`, `tests/test_grading_prompt.py` | `pytest tests/test_grading_prompt.py tests/test_grading_parser.py -q`. |

### Stream B Acceptance Criteria
- [ ] Prompt generation follows the same five logical prompt domains as the legacy script.
- [ ] One customer-day grade executes exactly five async prompt calls in parallel before merge.
- [ ] Partial outputs are validated at the prompt-domain level before final merge.
- [ ] Final merge still produces canonical Phase 3 `GradingOutput`.
- [ ] One prompt-domain failure maps cleanly to a controlled parser/provider failure path.
- [ ] Stream B tests cover both success and prompt-specific failure cases.

## Stream C - Pipeline Integration and Runtime Compatibility

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.35.12 - Service - Integrate file-based multi-prompt execution into grade_customer_day orchestration - Stream C (Dependent)` | Replace the single-prompt path in the pipeline with file-based multi-prompt execution while preserving the explicit Phase 3 result model. | `P2.35.10` | `app/services/grading_pipeline.py`, `app/services/grading_provider.py`, `app/services/grading_prompt.py` | Pipeline tests for success, provider failure, parse failure, and empty-transcript behavior. |
| C.2 | `P2.35.13 - Service - Update provider and mock runtime contracts for prompt-pack execution - Stream C (Dependent)` | Ensure mock and OpenAI-compatible providers support prompt-pack execution, prompt metadata, and prompt version reporting. | `P2.35.12` | `app/services/grading_provider.py`, `app/core/constants.py`, `app/core/config.py` (if version settings are surfaced) | Tests for default mock path and provider request payload structure across prompt domains. |
| C.3 | `P2.35.14 - Test - Add end-to-end grading pipeline tests for file-based multi-prompt execution - Stream C (Dependent)` | Add deterministic end-to-end coverage for prompt-pack-driven grading from transcript to persisted canonical grade. | `P2.35.13` | `tests/test_grading_pipeline.py`, `tests/conftest.py` (if fixture extensions are needed) | `pytest tests/test_grading_pipeline.py -q`. |

### Stream C Acceptance Criteria
- [ ] `grade_customer_day()` uses the file-based multi-prompt path instead of the inline single prompt.
- [ ] Mock and external provider adapters remain compatible with the new prompt execution model.
- [ ] The explicit `EMPTY_TRANSCRIPT` / `PROVIDER_ERROR` / `PARSE_ERROR` contract remains unchanged at the pipeline boundary.
- [ ] Stream C tests cover runtime behavior end to end.

## Stream D - Validation, Docs, and Phase 4 Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.35.15 - QA - Run compile and targeted pytest verification for prompt-pack refactor scope - Stream D (Dependent)` | Execute compile and targeted grading tests covering prompt assets, prompt parsing, and pipeline behavior. | `P2.35.11`, `P2.35.14` | No mandatory code files; QA notes in task records | `python -m compileall app tests` and targeted grading prompt/parser/pipeline pytest suites. |
| D.2 | `P2.35.16 - Docs - Update task/progress docs and Phase 4 dependency notes after prompt refactor - Stream D (Dependent)` | Sync docs after execution/review and confirm that Phase 4 batch execution now depends on the externalized prompt-pack path. | `P2.35.15` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-3.5.md`, `docs/milestone-2/m2-phase-4.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Acceptance Criteria
- [ ] Compile checks pass for modified Python modules.
- [ ] Targeted prompt/parser/pipeline tests pass or any environment blocker is explicitly documented.
- [ ] Docs are synchronized with the refactor outcome and Phase 4 dependency state.

## Suggested Files by Concern
- Prompt assets:
  - `app/prompt_assets/grading/<version>/system_prompt.md`
  - `app/prompt_assets/grading/<version>/ai_performance_judge.md`
  - `app/prompt_assets/grading/<version>/conversation_health.md`
  - `app/prompt_assets/grading/<version>/user-signals.md`
  - `app/prompt_assets/grading/<version>/escalation.md`
  - `app/prompt_assets/grading/<version>/intent.md`
- Config/constants:
  - `app/core/config.py`
  - `app/core/constants.py`
  - `.env.example`
- Schemas:
  - `app/schemas/grading_prompts.py` (new)
  - `app/schemas/grading.py`
  - `app/schemas/__init__.py`
- Services:
  - `app/services/grading_prompt_assets.py` (new)
  - `app/services/grading_prompt.py`
  - `app/services/grading_parser.py`
  - `app/services/grading_provider.py`
  - `app/services/grading_pipeline.py`
  - `app/services/__init__.py`
- Tests:
  - `tests/test_grading_prompt_assets.py` (new)
  - `tests/test_grading_prompt.py`
  - `tests/test_grading_parser.py`
  - `tests/test_grading_pipeline.py`

## Component Dependency Summary
- Gate 3.5 defines the prompt-pack contract, settings, schemas, and module boundaries used by all streams.
- Stream A externalizes assets and loader behavior first because all runtime prompt execution depends on those files.
- Stream B depends on Stream A to build per-domain prompts from the asset pack and merge prompt-domain outputs.
- Stream C depends on Stream B because pipeline orchestration should integrate the real multi-prompt path, not a placeholder.
- Stream D validates and documents the prompt refactor before Phase 4 execution begins.
- Phase 4 remains blocked until Stream D completes.

## Parallelization Map

```text
Gate 3.5 (P2.35.1 - P2.35.5 prompt-pack contract + scaffolds) -------+
                                                                       |
  |- Stream A (prompt assets + loader) ----------------------------->  |
                                                                       |
  |- Stream B (multi-prompt build + merge) ------------------------->  |  (after A)
                                                                       |
  |- Stream C (pipeline integration + provider compatibility) ------>  |  (after B)
                                                                       |
  |- Stream D (compile/tests/docs handoff) ------------------------->  |  (after C)
                                                                       v
          Phase 3.5 Complete (Prompt Externalization and Legacy Multi-Prompt Alignment)
```

## Definition of Done (Phase 3.5)
- [ ] Runtime grading prompts are externalized into versioned markdown assets.
- [ ] The grading pipeline follows a five-domain prompt flow aligned to the legacy generator structure.
- [ ] Prompt parsing and merge still produce canonical Phase 3 `GradingOutput`.
- [ ] Prompt versioning and prompt asset validation are deterministic and startup/test safe.
- [ ] The explicit pipeline failure-result contract remains unchanged.
- [ ] Targeted prompt/parser/pipeline tests exist and pass for modified scope.
- [ ] No lint/syntax errors exist in modified Python modules.

## Test Scenarios (Phase 3.5 Validation)

### Happy Path
- Active prompt pack loads all required markdown assets successfully.
- One customer-day transcript is rendered into five prompt-domain requests with correct placeholder substitution.
- Five valid prompt-domain outputs merge into one canonical `GradingOutput`.
- Mock provider path still succeeds end to end with the prompt-pack-driven runtime.

### Edge Cases
- Missing prompt file or placeholder mismatch fails fast before grading execution.
- One malformed prompt-domain response yields a controlled parser failure without partial grade persistence.
- Legacy label-only intent output is normalized deterministically or rejected explicitly per the finalized merge contract.
- Prompt asset root/version misconfiguration fails startup/config validation clearly.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- The legacy markdown prompts are the right starting point for runtime prompt externalization, but they may be revised to satisfy the canonical Phase 3 persistence contract.
- Runtime prompt assets should live in an app-owned versioned directory rather than depend on repo-root file paths.
- Prompt-domain execution is explicit: one customer-day grade uses five async prompt calls in parallel, followed by deterministic merge and validation.
- Phase 4 batch execution should wait for prompt-pack versioning to stabilize first.

### Open Questions
- None currently. Gate 3.5 locked the initial runtime direction on `2026-03-09`:
  - app-owned versioned prompt packs may revise wording where needed for strict canonical output
  - the intent prompt remains label-based in the prompt pack, with deterministic label-to-code normalization during merge

## Estimated Duration (Units)
- Gate 3.5 (`P2.35.1` - `P2.35.5`): `2.0`
- Stream A (`P2.35.6` - `P2.35.8`): `1.25`
- Stream B (`P2.35.9` - `P2.35.11`): `1.75`
- Stream C (`P2.35.12` - `P2.35.14`): `1.75`
- Stream D (`P2.35.15` - `P2.35.16`): `0.75`
- Sequential total: `7.5`
- Parallelized total after Gate (A -> B -> C -> D): `~5.75 - 6.0`

## Done Condition for Phase 3.5 Planning
Phase 3.5 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-3.5.md`).
- The inserted phase is reflected in `docs/tasks.md`, `docs/project-progress.md`, and milestone dependency notes.
- Prompt externalization tasks are atomic, dependency-linked, and execution-ready.
- Phase 4 is explicitly downstream of this prompt refactor phase.
