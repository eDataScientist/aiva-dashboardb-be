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

## Phase Ordering (High-Level)
- Data contract and migrations should come before auth implementation.
- The data-contract phase should include models needed for auth/accounts as well as Milestone 2 grading/monitoring support.
- Auth/accounts foundation should follow the data-contract phase.

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
- Historical highlight behavior after config changes (current-rules view vs historical-rules view) is not yet finalized.
