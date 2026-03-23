# OpenRouter Nightly Grading Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make production deployment reliably run nightly grading with OpenRouter on `minimax/minimax-m2.5` at `01:00 GST`, without changing the safe local defaults.

**Architecture:** Reuse the existing `openai_compatible` provider path and tighten the deployment contract around it. Add a small settings normalization layer so `OPENROUTER_API_KEY` can satisfy the provider requirement when the deployment uses OpenRouter naming, then update env/docs to show the exact scheduler and provider values required in production.

**Tech Stack:** FastAPI, Pydantic Settings, HTTPX, pytest

---

## Chunk 1: Config and Provider Contract

### Task 1: Add failing tests for OpenRouter-compatible settings

**Files:**
- Modify: `tests/test_grading_config.py`
- Modify: `tests/test_grading_parser.py`

- [ ] **Step 1: Write the failing config test**

Add a settings test asserting that `OPENROUTER_API_KEY` is accepted when:
- `GRADING_PROVIDER=openai_compatible`
- `GRADING_API_KEY` is unset

- [ ] **Step 2: Run the failing config test**

Run: `pytest tests/test_grading_config.py -q -k openrouter`
Expected: FAIL because the current settings model ignores `OPENROUTER_API_KEY` for provider validation.

- [ ] **Step 3: Write the failing provider test**

Add a provider test asserting that the OpenAI-compatible transport receives the resolved API key and configured OpenRouter base URL.

- [ ] **Step 4: Run the failing provider test**

Run: `pytest tests/test_grading_parser.py -q -k openrouter`
Expected: FAIL because the resolved API key is currently unavailable through OpenRouter naming.

### Task 2: Implement minimal settings compatibility

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Add an `openrouter_api_key` settings field**
- [ ] **Step 2: Normalize it like the other optional provider fields**
- [ ] **Step 3: Resolve `grading_api_key` from `GRADING_API_KEY` first, then `OPENROUTER_API_KEY`**
- [ ] **Step 4: Keep the mock-provider scheduler safety guard intact**

- [ ] **Step 5: Run targeted tests**

Run: `pytest tests/test_grading_config.py tests/test_grading_parser.py -q`
Expected: PASS

## Chunk 2: Deployment Contract

### Task 3: Update env example for explicit nightly OpenRouter deployment

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Keep safe local defaults**
- [ ] **Step 2: Add commented production guidance for**
  - `GRADING_PROVIDER=openai_compatible`
  - `GRADING_BASE_URL=https://openrouter.ai/api/v1`
  - `GRADING_MODEL=minimax/minimax-m2.5`
  - `GRADING_BATCH_SCHEDULER_ENABLED=true`
  - `GRADING_BATCH_SCHEDULER_HOUR_GST=1`

### Task 4: Update Phase 8 docs

**Files:**
- Modify: `docs/milestone-2/m2-phase-8.md`
- Modify: `docs/project-progress.md`
- Modify: `docs/tasks.md`

- [ ] **Step 1: Correct the provider contract so docs match runtime**
- [ ] **Step 2: Document the exact production env values for OpenRouter nightly grading**
- [ ] **Step 3: Record that the prior deploy was intentionally safe but not scheduler-enabled**

## Chunk 3: Verification and Handoff

### Task 5: Verify the patch

**Files:**
- Modify: none unless verification exposes a real issue

- [ ] **Step 1: Run compile checks**

Run: `python -m compileall app tests`
Expected: PASS

- [ ] **Step 2: Run targeted pytest**

Run: `pytest tests/test_grading_config.py tests/test_grading_parser.py -q`
Expected: PASS

- [ ] **Step 3: Prepare deployment handoff**

Produce the exact server `.env` values needed for:
- OpenRouter
- `minimax/minimax-m2.5`
- nightly `01:00 GST` scheduler
