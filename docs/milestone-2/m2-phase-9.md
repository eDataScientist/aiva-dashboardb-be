# Milestone 2 - Phase 9 Plan: OpenAI SDK Transport Cutover

## Goals
- Replace the custom `httpx`-based grading transport with the official OpenAI SDK (`AsyncOpenAI`) so the backend runtime uses the same proven client stack as the legacy export script.
- Preserve the existing `openai_compatible` provider enum, config contract, scheduler, batch execution, and API surface -- the change is internal to the transport layer.
- Support both direct OpenAI and OpenRouter as co-equal production profiles through the same `AsyncOpenAI` SDK, switchable via config only (`GRADING_BASE_URL` and `GRADING_MODEL`).

## Problem Statement
- The backend runtime grades through `app/services/grading_provider.py`, which uses a custom `httpx` transport (`_default_openai_compatible_transport`) to make OpenAI-compatible chat completion requests.
- The legacy export script (`generate_conversation_grades.py`) uses the official `openai` SDK (`AsyncOpenAI`) and has been consistently reliable.
- Replay evidence on the same nightly-failure conversations:
  - Backend runtime (`httpx` + OpenRouter/Minimax): one conversation succeeded 3/10, one succeeded 0/10.
  - Legacy script (`AsyncOpenAI` + direct OpenAI `gpt-4o-mini`): both conversations succeeded 10/10.
- The reliability gap is attributable to two variables: the transport layer (`httpx` vs `AsyncOpenAI`) and the provider/model (OpenRouter + Minimax vs direct OpenAI + `gpt-4o-mini`). This phase addresses both by adopting the SDK and updating the recommended production model.
- The OpenAI SDK natively supports custom `base_url`, so OpenRouter remains usable through the same `AsyncOpenAI` client without a separate transport implementation.

## Planning Analysis (Required Order)

### 1) Data Models
- No schema changes. `conversation_grades`, `grading_runs`, and `grading_run_items` remain unchanged.
- `grading_runs` already persists `provider`, `model`, and `prompt_version` per run, which is sufficient to distinguish pre- and post-cutover runs.

### 2) Migration
- No migration required. The existing `grading_runs` columns capture all runtime context needed for incident review.

### 3) Dependencies
- The `openai` SDK becomes a production dependency in `requirements.txt` (currently only used by the standalone export script).
- `httpx` remains a dependency for other parts of the application but is no longer used by the grading transport.
- The `GradingProvider` protocol, `GradingProviderRequest` dataclass, `MockGradingTransport` protocol, retry wrapper, and mock transport in `grading_provider.py` are unchanged.
- The scheduler, manual backfill flow, batch execution, and all downstream APIs continue to call the same orchestration surface.

### 4) Configuration
- The `GRADING_PROVIDER` enum values (`mock`, `openai_compatible`) remain the same. No new provider families are introduced -- the SDK handles both direct OpenAI and OpenRouter via `base_url`.
- Existing config fields used by the new transport:
  - `GRADING_API_KEY` / `OPENROUTER_API_KEY` -- passed to `AsyncOpenAI(api_key=...)`
  - `GRADING_BASE_URL` -- passed to `AsyncOpenAI(base_url=...)`. Defaults to `None` (SDK default: `https://api.openai.com/v1`).
  - `GRADING_MODEL` -- passed to `client.chat.completions.create(model=...)`
  - `GRADING_REQUEST_TIMEOUT_SECONDS` -- passed to `AsyncOpenAI(timeout=...)`
- Both direct OpenAI and OpenRouter are co-equal production options. Switching between them requires only changing `GRADING_BASE_URL`, `GRADING_MODEL`, and `GRADING_API_KEY`.

### 5) Endpoints
- No endpoint changes. All existing grading run trigger, history, metrics, monitoring, and dashboard endpoints remain stable.

## Dependencies
- Phase dependency: `Milestone 2 Phase 8 deployment readiness -> Milestone 2 Phase 9`
- Upstream features reused unchanged:
  - Phase 3 grading extraction, prompting, parser, and orchestration
  - Phase 3.5 prompt-pack assets
  - Phase 4 batch execution, scheduler, and run ledger
  - Phase 5+ APIs that consume `conversation_grades` and `grading_runs`
- Downstream impact:
  - Nightly scheduler reliability (primary motivation)
  - Manual backfill/operator reruns (same transport improvement)

## Phase 9 Success Criteria
- Backend grading transport uses `AsyncOpenAI` from the official `openai` SDK instead of raw `httpx`.
- All existing grading pipeline, batch, scheduler, and API tests pass without modification (or with minimal transport-mock adjustments).
- Production deployment docs present direct OpenAI and OpenRouter as co-equal profiles, switchable via config only.
- Nightly grading run completes successfully on the new transport.

## Test Impact Analysis

### Transport layer boundary
The grading provider factory (`build_grading_provider`) accepts optional injection parameters: `mock_transport` and `openai_transport`. All existing tests inject fake transport functions through these parameters or use the built-in mock provider. No test directly instantiates `httpx.AsyncClient` or calls the real `_default_openai_compatible_transport`.

This means the transport swap is behind the injection boundary -- the `_default_openai_compatible_transport` function is replaced, but no test calls it directly.

### Test files unaffected (no changes needed)
These test files operate above the transport layer and will not require any modification:

| File | Tests | Why unaffected |
|---|---|---|
| `test_grading_pipeline.py` | 8 | Uses `build_grading_provider(settings=mock)` or inline async functions as providers. Never touches the real transport. |
| `test_grading_batch.py` | 17 | Mocks at the pipeline/extraction level, not the transport level. Uses mock provider settings. |
| `test_grading_run_services.py` | 8 | Tests run service logic and permissions. Provider is config-only. |
| `test_grading_scheduler.py` | 3 | Mocks the batch runner (`AsyncMock`). No transport involvement. |
| `test_grading_config.py` | 17 | Tests `Settings` validation. Provider enum values (`mock`, `openai_compatible`) are unchanged. |
| `test_grading_extraction.py` | -- | Tests transcript extraction from raw chats. No provider involvement. |
| `test_grading_prompt.py` | -- | Tests prompt building. No provider involvement. |
| `test_grading_prompt_assets.py` | -- | Tests prompt-pack file validation. No provider involvement. |
| `test_grading_schemas.py` | -- | Tests Pydantic schemas. No provider involvement. |
| `test_grading_metrics*.py` | -- | Tests metrics queries. No provider involvement. |
| `test_grading_monitoring*.py` | -- | Tests monitoring queries. No provider involvement. |
| `test_grading_dashboard*.py` | -- | Tests dashboard queries. No provider involvement. |
| `test_grading_runs_api.py` | -- | Tests API routes. No provider involvement. |

### Tests to review (may need adjustment)
These tests in `test_grading_parser.py` inject fake transports via `build_grading_provider(openai_transport=...)`:

| Test | What it does | Impact |
|---|---|---|
| `test_build_grading_provider_surfaces_openai_transport_results` | Injects `fake_openai_transport(request, settings) -> str` via `openai_transport=` parameter. Asserts the provider returns the fake's output and that `settings.grading_api_key` was passed through. | **No change needed** if the `OpenAICompatibleTransport` protocol signature `(request, settings) -> str` is preserved. The test never touches `httpx` or `AsyncOpenAI` -- it injects its own function. |
| `test_build_grading_provider_uses_openrouter_api_key_alias` | Same injection pattern. Asserts `openrouter_api_key` resolves to `grading_api_key` and `base_url` is passed through settings. | **No change needed** -- same reasoning. |
| `test_build_grading_provider_passes_prompt_pack_metadata_to_openai_transport` | Same injection pattern. Asserts prompt metadata (`prompt_key`, `prompt_version`, `template_file`, `prompt_sequence`) is passed through to the transport. | **No change needed** -- same reasoning. |
| `test_build_grading_provider_retries_mock_transport_failures` | Injects `flaky_transport` via `mock_transport=` parameter. Tests retry logic with `GradingProviderError`. | **No change needed** -- mock transport path is untouched. |

### Key design decision for tests
The `OpenAICompatibleTransport` protocol in `grading_provider.py:39-44` defines the injection signature:

```python
class OpenAICompatibleTransport(Protocol):
    async def __call__(
        self, request: GradingProviderRequest, settings: Settings,
    ) -> str: ...
```

**This protocol must be preserved.** The implementation behind `_default_openai_compatible_transport` changes from `httpx` to `AsyncOpenAI`, but the factory's `openai_transport=` injection parameter keeps the same signature. This means:
- All 3 existing `openai_transport=` tests pass without changes.
- All 1 existing `mock_transport=` retry test passes without changes.
- The 10 parser-only tests in the same file are completely unrelated to transport.

### New tests to add
Phase 9 should add targeted tests for the new `AsyncOpenAI`-backed default transport to cover behaviors that were previously covered by the `httpx` implementation:

| New test | Purpose |
|---|---|
| `test_default_openai_transport_raises_provider_error_on_timeout` | Verify `AsyncOpenAI` timeout exceptions are caught and wrapped as `GradingProviderError`. |
| `test_default_openai_transport_raises_provider_error_on_http_error` | Verify SDK HTTP status errors (e.g. 429, 500) are caught and wrapped as `GradingProviderError`. |
| `test_default_openai_transport_raises_provider_error_on_empty_content` | Verify empty completion content raises `GradingProviderError`. |
| `test_default_openai_transport_raises_provider_error_on_unexpected_payload` | Verify malformed SDK response raises `GradingProviderError`. |
| `test_default_openai_transport_passes_base_url_when_configured` | Verify `AsyncOpenAI(base_url=...)` is called when `GRADING_BASE_URL` is set (OpenRouter path). |
| `test_default_openai_transport_omits_base_url_when_not_configured` | Verify `AsyncOpenAI()` is called without `base_url` when `GRADING_BASE_URL` is not set (direct OpenAI path). |
| `test_default_openai_transport_sends_json_response_format` | Verify `response_format={"type": "json_object"}` is passed to `client.chat.completions.create()`. |

These tests should mock `AsyncOpenAI` at the class level (e.g. `unittest.mock.patch("app.services.grading_provider.AsyncOpenAI")`) to avoid real API calls while verifying the SDK is wired correctly.

### Test summary
- **Existing tests that need changes:** 0
- **Existing tests unaffected:** all (the `OpenAICompatibleTransport` protocol injection boundary isolates them)
- **New tests to add:** 7 (covering the `AsyncOpenAI` default transport error handling, config wiring, and request shape)

## Gate 9.0 - Transport Swap and Test Coverage

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 9.0.1 | `P2.9.1 - Deps - Add openai SDK as a production dependency` | Add `openai` to `requirements.txt` as a runtime dependency. Confirm it installs cleanly alongside existing deps and inside the Docker image. | None | `requirements.txt`, `Dockerfile` (rebuild verification) | `pip install -r requirements.txt` succeeds; `python -c "from openai import AsyncOpenAI"` succeeds; `docker compose build` succeeds. |
| 9.0.2 | `P2.9.2 - Service - Replace httpx transport with AsyncOpenAI in grading_provider.py` | Replace `_default_openai_compatible_transport` with an implementation that uses `AsyncOpenAI` for chat completions. Preserve the `OpenAICompatibleTransport` protocol signature so the `openai_transport=` injection parameter remains compatible. Preserve error classification (`GradingProviderError` for timeouts, HTTP errors, empty payloads, non-string content). Use `base_url` from settings when present (OpenRouter), omit it for direct OpenAI. | `P2.9.1` | `app/services/grading_provider.py` | `python -m compileall app`; all existing tests in `test_grading_parser.py` pass unchanged. |
| 9.0.3 | `P2.9.3 - Test - Add AsyncOpenAI default transport tests` | Add 7 new tests covering the `AsyncOpenAI`-backed default transport: timeout error wrapping, HTTP error wrapping, empty content handling, unexpected payload handling, `base_url` presence/absence, and `response_format` passthrough. Mock `AsyncOpenAI` at the class level to avoid real API calls. | `P2.9.2` | `tests/test_grading_parser.py` | `pytest tests/test_grading_parser.py -q` passes with new transport coverage. |
| 9.0.4 | `P2.9.4 - Test - Run full test suite and compile check` | Confirm the transport swap does not break any existing grading pipeline, batch execution, scheduler, metrics, monitoring, or dashboard tests. | `P2.9.3` | None (test-only) | `python -m compileall app tests`; `pytest -q` -- all tests pass. |

## Gate 9.1 - Deployment Update and Production Verification

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 9.1.1 | `P2.9.5 - Config - Update deployment docs and .env.example with co-equal OpenAI and OpenRouter profiles` | Update Phase 8 deployment docs and `.env.example` to present direct OpenAI and OpenRouter as co-equal production profiles, both using the `AsyncOpenAI` SDK. | `P2.9.4` | `.env.example`, `docs/milestone-2/m2-phase-8.md`, `docs/milestone-2/m2-phase-9.md` | Docs review confirms both profiles and switching instructions are clear. |
| 9.1.2 | `P2.9.6 - QA - Deploy, run production verification, and update progress docs` | Rebuild and redeploy the Docker image with the OpenAI SDK transport. Trigger or observe a nightly grading run. Confirm successful completion. Update task and progress docs. | `P2.9.5` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-9.md` | Deployed container starts cleanly; at least one grading run completes successfully on the new transport; docs reflect the cutover outcome. |

## Execution Order
1. Gate 9.0: Add the SDK dependency, swap the transport, add new transport tests, run full suite. Sequential within the gate.
2. Gate 9.1: Update deployment docs, deploy and verify in production. Sequential within the gate.

## Completion Status (`2026-03-24`)

### Gate 9.0 -- Transport Swap and Test Coverage
- **P2.9.1** -- Added `openai>=1.30.0,<2.0.0` to `requirements.txt`. Import verified.
- **P2.9.2** -- Replaced `_default_openai_compatible_transport` in `grading_provider.py`: `httpx.AsyncClient` replaced with `openai.AsyncOpenAI`. Error classification preserved (`GradingProviderError` for `APITimeoutError`, `APIStatusError`, `APIConnectionError`, empty/non-string content). `OpenAICompatibleTransport` protocol signature unchanged.
- **P2.9.3** -- Added 7 new tests in `test_grading_parser.py` covering timeout wrapping, HTTP error wrapping, empty content, unexpected payload, `base_url` presence/absence, and `response_format` passthrough. All mock `AsyncOpenAI` at class level.
- **P2.9.4** -- Full suite: **335 tests passed**, 0 failures. `compileall` clean.

### Gate 9.1 -- Deployment Update and Production Verification
- **P2.9.5** -- Updated `.env.example` and `m2-phase-8.md` to present direct OpenAI and OpenRouter as co-equal production profiles, both using the `AsyncOpenAI` SDK.
- **P2.9.6** -- Production deployment and nightly verification is pending operator action (rebuild Docker image with new `openai` SDK dependency and update `.env` to direct OpenAI credentials).

### Files Modified
| File | Action | Purpose |
|---|---|---|
| `requirements.txt` | Modified | Added `openai>=1.30.0,<2.0.0` as production dependency |
| `app/services/grading_provider.py` | Modified | Replaced `httpx` transport with `AsyncOpenAI` SDK client |
| `tests/test_grading_parser.py` | Modified | Added 7 new `AsyncOpenAI` transport tests |
| `.env.example` | Modified | Updated production profile to direct OpenAI + `gpt-4o-mini` |
| `docs/milestone-2/m2-phase-8.md` | Modified | Updated deployment docs with new production/rollback profiles |
| `docs/milestone-2/m2-phase-9.md` | Modified | Added completion status |

## Rollback Path
- If the new transport causes production failures, rollback is a config change:
  1. Set `GRADING_BASE_URL=https://openrouter.ai/api/v1`
  2. Set `GRADING_MODEL=minimax/minimax-m2.5`
  3. Set `GRADING_API_KEY` to the OpenRouter key
  4. Restart the container: `docker compose build && docker compose up -d`
- The `AsyncOpenAI` client handles OpenRouter identically via `base_url`, so no code rollback is needed.
