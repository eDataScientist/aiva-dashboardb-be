# OpenRouter Nightly Grading Design

**Date:** 2026-03-23

**Goal:** Enable production deployment to run the nightly previous-day grading batch against a real AI model via OpenRouter, while keeping local/test defaults safe.

## Scope

- Keep the existing `openai_compatible` provider runtime.
- Align deployment docs and env examples with the actual runtime contract.
- Reduce production misconfiguration risk by allowing `OPENROUTER_API_KEY` to satisfy the OpenAI-compatible API-key requirement when `GRADING_API_KEY` is unset.
- Preserve the current scheduler semantics: previous GST day at `01:00 GST`.

## Design

### Provider Path

The backend already supports an OpenAI-compatible transport. OpenRouter should continue to use that path rather than adding a separate provider type. Production deployment should therefore use:

- `GRADING_PROVIDER=openai_compatible`
- `GRADING_BASE_URL=https://openrouter.ai/api/v1`
- `GRADING_MODEL=minimax/minimax-m2.5`
- `GRADING_API_KEY=<key>` or `OPENROUTER_API_KEY=<key>`

### Scheduler Path

The scheduler is already implemented and started from the FastAPI lifespan. No scheduler code changes are required beyond configuration compatibility. Production deployment should explicitly set:

- `GRADING_BATCH_SCHEDULER_ENABLED=true`
- `GRADING_BATCH_SCHEDULER_HOUR_GST=1`

### Safety

- Local/test defaults remain `GRADING_PROVIDER=mock` and `GRADING_BATCH_SCHEDULER_ENABLED=false`.
- Non-test scheduled execution continues to reject the mock provider unless the explicit mock override is enabled.

## Verification

- Add config tests proving OpenRouter key aliasing works.
- Add provider tests proving the OpenAI-compatible path sees the resolved OpenRouter credentials/base URL/model settings.
- Update deployment docs and env examples so the server-side configuration is explicit.
