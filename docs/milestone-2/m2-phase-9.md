# Milestone 2 - Phase 9 Plan

## Goals
- Replace the current ambiguous production grading runtime with an explicit, measurable provider strategy that favors reliability over nominal provider flexibility.
- Promote a first-class direct OpenAI runtime path in the backend instead of keeping the official SDK isolated in the legacy export script.
- Preserve the existing customer-day grading, run ledger, scheduler, and API contracts unless a clear operational gap requires additive telemetry.
- Leave deployment in a state where nightly grading can be cut over safely with a documented replay benchmark, rollout sequence, and rollback path.

## Problem Statement
- The backend runtime currently grades through `app/services/grading_provider.py`, which uses a custom `httpx` `openai_compatible` transport.
- Production was configured around OpenRouter plus `minimax/minimax-m2.5`, so the app never adopted the direct OpenAI SDK path that already exists in `generate_conversation_grades.py`.
- Recent replay evidence shows a material reliability gap on the same nightly-failure conversations:
  - app runtime path + OpenRouter/Minimax replay: one conversation succeeded `3/10`, one succeeded `0/10`
  - legacy script path + direct OpenAI `gpt-4o-mini` replay: both conversations succeeded `10/10`
- That evidence is directionally strong but not yet sufficient to justify a blind production swap because two variables changed at once:
  - transport/client stack (`httpx` vs `AsyncOpenAI`)
  - provider/model (`OpenRouter + Minimax` vs direct OpenAI + `gpt-4o-mini`)

## Planning Analysis (Required Order)

### 1) Data Models
- `conversation_grades` remains the canonical grade fact table.
  - No score/rubric schema changes are required for this revision.
  - The revision should not change the customer-day grain, identity model, or upsert behavior.
- `grading_runs` and `grading_run_items` remain the operational evidence source.
  - Existing `settings_snapshot`, run counters, and error fields should be reused first.
  - Additional persistent metadata should only be introduced if current run snapshots cannot capture the active provider, model, transport, timeout, and retry policy clearly enough for incident review.
- The replay corpus should be built from existing raw chats plus failed `grading_run_items`, not from a new staging table.

### 2) Migration
- Default path: no migration.
- Gate review should explicitly confirm whether current run snapshots can capture:
  - provider family
  - transport implementation
  - model
  - base URL
  - timeout/retry policy
- If those values can be stored in the existing snapshot payload, no Alembic change should be added.
- A migration is only justified if provider-comparison telemetry cannot be made reviewable without new bounded columns or indexes.

### 3) Dependencies
- The runtime should treat the official `openai` SDK as a production dependency, not as a script-only dependency.
- The backend should keep one provider abstraction, but it should expose explicit provider families instead of one overloaded `openai_compatible` mode.
- The current custom `httpx` path may remain as:
  - a compatibility transport for OpenRouter, or
  - a fallback only
- The scheduler, manual backfill flow, and run history APIs should continue to call the same orchestration surface after the provider refactor.

### 4) Configuration
- The revision should replace the ambiguous production contract with explicit settings:
  - direct OpenAI provider mode
  - OpenRouter provider mode
  - provider-specific API key/base URL/header rules
  - explicit retry and timeout settings
- Startup validation should fail fast on invalid combinations such as:
  - OpenAI provider with an OpenRouter-only model
  - OpenRouter provider without a base URL
  - scheduler enabled on mock or unsupported provider combinations
- Cutover config should default production toward the direct OpenAI path once replay evidence is approved.

### 5) Endpoints
- No public route additions are required for the first pass.
- Existing grading run trigger/history endpoints should remain stable.
- If the current run-detail response cannot expose enough runtime context for operations, Phase 8 Revision may add additive observability fields to existing run payloads, but no route split is planned.

## Dependencies
- Phase dependency: `Milestone 2 Phase 8 deployment readiness -> Milestone 2 Phase 9`
- Upstream features reused unchanged:
  - Phase 3 grading extraction, prompting, parser, and orchestration
  - Phase 3.5 prompt-pack assets
  - Phase 4 batch execution, scheduler, and run ledger
  - Phase 5+ APIs that consume `conversation_grades` and `grading_runs`
- Downstream impact:
  - nightly scheduler reliability
  - manual backfill/operator reruns
  - deployment documentation and provider secret handling

## Revision Success Criteria
- Backend runtime supports a first-class direct OpenAI provider path using the official SDK.
- OpenRouter remains explicit rather than being hidden behind a generic compatibility mode.
- A controlled replay corpus compares direct OpenAI and OpenRouter paths using the same backend orchestration contract.
- Production cutover is gated by measured replay results, not by anecdotal single-run success.
- Nightly scheduler rollout and rollback steps are documented and reversible.

## Gate 9.0 - Provider Contract and Cutover Baseline

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 9.0.1 | `P2.9.1 - Design - Finalize provider acceptance criteria and comparison corpus - Gate (Independent)` | Define what counts as a production-worthy provider path, including replay corpus composition, success/error thresholds, and acceptable rollback triggers. | None | `docs/milestone-2/m2-phase-9.md`, `docs/milestone-2/milestone-notes.md` | Review checklist confirms transport/provider variables are separated and cutover criteria are explicit. |
| 9.0.2 | `P2.9.2 - DB - Validate no migration path and runtime metadata capture strategy - Gate (Dependent)` | Confirm whether current run snapshots can capture provider/model/transport/runtime settings without additive schema work; document the no-migration or additive-migration decision. | `P2.9.1` | `docs/milestone-2/m2-phase-9.md`, `app/models/grading_runs.py`, `alembic/versions/*.py` (conditional) | Schema review or migration smoke if a revision is required. |
| 9.0.3 | `P2.9.3 - Config - Define explicit provider enums, env contract, and cutover defaults - Gate (Dependent)` | Replace `openai_compatible` ambiguity with explicit provider families and validate safe production defaults for direct OpenAI and OpenRouter. | `P2.9.1` | `app/core/constants.py`, `app/core/config.py`, `.env.example`, `tests/test_grading_config.py` | Config validation tests for valid/invalid provider combinations and scheduler safety. |
| 9.0.4 | `P2.9.4 - API - Confirm no-route-change policy and required run-observability contract - Gate (Dependent)` | Freeze the external route surface unless additive run-detail metadata is required, and define the minimum operator-visible runtime context. | `P2.9.1`, `P2.9.2`, `P2.9.3` | `docs/milestone-2/m2-phase-9.md`, `app/schemas/grading_runs.py` (conditional), `tests/test_grading_runs_api.py` (conditional) | Schema/API review confirms either no route change or bounded additive observability. |
| 9.0.5 | `P2.9.5 - Service - Finalize provider abstraction and transport rollout architecture - Gate (Dependent)` | Lock the service boundary so Streams A-C can implement provider transports, orchestration wiring, and replay validation in parallel without conflicting interfaces. | `P2.9.2`, `P2.9.3`, `P2.9.4` | `app/services/grading_provider.py`, `app/services/__init__.py`, `tests/test_grading_parser.py`, `tests/test_grading_pipeline.py` | Import/compile smoke plus contract review for provider abstraction shape. |

## Stream A - Provider Transport Refactor

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.9.6 - Service - Add official OpenAI SDK transport for direct OpenAI grading - Stream A (Dependent)` | Introduce an official SDK-backed transport used by the backend runtime for direct OpenAI requests. | `P2.9.5` | `app/services/grading_provider.py`, `requirements.txt`, `tests/test_grading_parser.py`, `tests/test_grading_pipeline.py` | Deterministic transport tests plus compile coverage. |
| A.2 | `P2.9.7 - Service - Isolate explicit OpenRouter transport and provider-specific request rules - Stream A (Dependent)` | Keep OpenRouter support explicit, including provider-specific base URL and header handling, without conflating it with direct OpenAI. | `P2.9.6` | `app/services/grading_provider.py`, `app/core/config.py`, `.env.example`, `tests/test_grading_config.py`, `tests/test_grading_parser.py` | Provider-selection tests and request-shape assertions. |
| A.3 | `P2.9.8 - Test - Add provider adapter failure-classification and retry tests - Stream A (Dependent)` | Lock transport-specific timeout, empty-payload, parse, and retry behavior so production failures stay classifiable after the refactor. | `P2.9.7` | `tests/test_grading_parser.py`, `tests/test_grading_pipeline.py`, `tests/test_grading_config.py` | Targeted pytest for transport and pipeline slices. |

## Stream B - Orchestration, Scheduler, and Config Cutover

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.9.9 - Service - Wire explicit provider selection through grading pipeline, batch runs, and scheduler snapshots - Stream B (Dependent)` | Ensure manual runs and nightly runs use the new provider contract and persist enough runtime context for later incident review. | `P2.9.5`, `P2.9.6`, `P2.9.7` | `app/services/grading_pipeline.py`, `app/services/grading_batch.py`, `app/services/grading_runs.py`, `tests/test_grading_batch.py`, `tests/test_grading_runs.py`, `tests/test_grading_pipeline.py` | Service tests covering manual and scheduled paths under explicit providers. |
| B.2 | `P2.9.10 - Config - Update deployment defaults, env docs, and startup validation for direct OpenAI cutover - Stream B (Dependent)` | Make the safe production profile explicit, including direct OpenAI defaults, OpenRouter fallback semantics, and invalid-combination startup failures. | `P2.9.3`, `P2.9.9` | `.env.example`, `docs/milestone-2/m2-phase-8.md`, `docs/milestone-2/m2-phase-9.md`, `tests/test_grading_config.py` | Config tests plus docs review against the intended production profile. |
| B.3 | `P2.9.11 - Test - Add replay harness coverage for backend runtime direct OpenAI and OpenRouter paths - Stream B (Dependent)` | Turn the ad hoc replay investigation into a repeatable backend-side validation harness that exercises the same orchestration entry points under both provider families. | `P2.9.9`, `P2.9.10` | `tests/` or `scripts/` replay harness files, `docs/milestone-2/m2-phase-9.md` | Repeatable replay command documented with captured success/failure breakdowns. |

## Stream C - Reliability Benchmark and Rollout Evidence

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.9.12 - QA - Build historical failure corpus and benchmark providers on the same transcript set - Stream C (Dependent)` | Create a representative replay set from nightly failures, backlog failures, and successful controls so provider comparisons are statistically more useful than a two-conversation spot check. | `P2.9.1`, `P2.9.11` | `exports/` benchmark artifacts, `docs/milestone-2/m2-phase-9.md` | Benchmark report includes success rate, provider error rate, parse error rate, and run-time distribution by provider. |
| C.2 | `P2.9.13 - QA - Run controlled dry-run/nightly validation and define go-no-go threshold - Stream C (Dependent)` | Execute the selected direct OpenAI runtime in a production-like dry run before scheduler cutover and document the exact promotion/rollback criteria. | `P2.9.9`, `P2.9.12` | `docs/milestone-2/m2-phase-9.md`, deployment runbook notes | Validation checklist covers replay, one-off manual run, and first scheduled-run observation. |
| C.3 | `P2.9.14 - Docs - Update provider runbook, rollout steps, and rollback procedures - Stream C (Dependent)` | Produce the operator-facing instructions for secret management, redeploy, log verification, and emergency fallback between direct OpenAI and OpenRouter. | `P2.9.10`, `P2.9.13` | `docs/milestone-2/m2-phase-8.md`, `docs/milestone-2/m2-phase-9.md`, `docs/project-progress.md` | Runbook review confirms rollout is executable without tribal knowledge. |

## Stream D - Final Verification and Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.9.15 - QA - Run compile, full pytest, and provider replay verification for the reliability refactor - Stream D (Dependent)` | Verify the refactor end to end before any production cutover recommendation is made. | `P2.9.8`, `P2.9.11`, `P2.9.13` | `app/`, `tests/`, benchmark artifacts | `python -m compileall app tests`, `pytest -q`, and the documented replay benchmark all pass at the agreed threshold. |
| D.2 | `P2.9.16 - Docs - Update task/progress docs with cutover outcome and residual risks - Stream D (Dependent)` | Synchronize the final provider decision, validation evidence, and any residual operational risks into the canonical project docs. | `P2.9.15` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-9.md` | Docs review confirms the milestone handoff reflects the actual rollout state. |

## Recommended Execution Order
1. Complete Gate 9.0R to lock the provider contract and no-migration decision.
2. Run Stream A and Stream B in parallel once the transport abstraction is frozen.
3. Use Stream C to benchmark the explicit provider paths on the same corpus before changing production defaults.
4. Only after Stream C evidence is acceptable should Stream D recommend a production cutover.

## Immediate Review Notes
- The current `10/10` replay on direct OpenAI should be treated as a strong signal, not a final production readiness proof.
- The corrective action is not "swap to the script"; it is "move the backend runtime onto an explicit, measurable provider architecture and promote the better path once the backend replay corpus confirms it."
- The highest-risk anti-pattern is keeping one generic `openai_compatible` mode while silently pointing it at different providers; this revision should remove that ambiguity.
