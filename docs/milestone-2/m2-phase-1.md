# Milestone 2 - Phase 1 Plan: Data Contract and Migrations (Milestone 2 + Auth Models)

## Goals
- Finalize the Milestone 2 backend data contract required for grading, monitoring, and downstream metrics APIs.
- Introduce additive schema changes for `conversation_grades` to support canonical identity and intent normalization.
- Add configurable highlight-rules storage (while keeping highlights computed on read).
- Add auth/account/profile data models and migrations required before auth implementation in Phase 2.
- Keep raw chat/source tables untouched and maintain non-destructive migration behavior.

## Planning Analysis (Required Order)

### 1) Data Models
- `conversation_grades` remains the primary grade fact table for Milestone 2.
- Monitoring/read model direction for Milestone 2:
  - New monitoring endpoints operate on a **customer-day** (conversation-day) grain.
  - Full conversation view (across time) remains a separate endpoint surface.
- Raw chat table policy:
  - No `conversation_grade_id` added to raw chat rows.
  - Grade-to-message association is derived via canonical identity + GST day.
- Grade identity model direction:
  - Move business key toward `conversation_identity + grade_date`.
  - Add explicit identity source/type semantics (e.g. phone/email/session).
  - Preserve backward compatibility during migration transition from `phone_number`-only rows.
- Intent storage direction (confirmed):
  - `intent_code` (authoritative)
  - `intent_label` (display)
  - `intent_reasoning` (AI reasoning)
- Highlights handling direction (confirmed):
  - Highlights are computed on read in service layer.
  - A separate DB table stores configurable highlight thresholds/rules.
  - No highlight flags are persisted on `conversation_grades` in v1.
- Auth/profile model direction (Phase 1 scope):
  - Add account and profile persistence models required for Phase 2 auth implementation.
  - Phase 1 defines schema contract only; auth flow endpoints/guards are Phase 2.
  - Confirmed baseline decisions:
    - login uses `email + password`
    - store password hash only (no plaintext password storage)
    - use a single account table for auth + minimal profile data in v1
    - roles required: `super_admin`, `company_admin`, `analyst`
    - `company_admin` is role-only in v1 (no company/tenant linkage required in Phase 1 schema)
    - login-only scope for Milestone 2 auth (password reset/change deferred)
  - Final auth transport (JWT vs sessions) may affect Phase 2 endpoint implementation, but Phase 1 schema should avoid unnecessary token/session tables unless required.

### 2) Migration
- Phase 1 should use additive-only migrations and avoid destructive changes to raw source data.
- `conversation_grades` migration work is expected to include:
  - new canonical identity fields
  - `intent_code`
  - new indexes for future monitoring filters/sorts
  - compatibility-safe backfill/normalization strategy where possible
- Highlight rules configuration should be introduced via a dedicated table and default seeded rule set/config row (final shape to be finalized).
- Auth/account/profile tables should be introduced in a separate migration (or clearly separated revision block) to keep rollback/review simple.
- Migration validation should include upgrade/downgrade checks on a clean local DB and compatibility checks against existing Milestone 1 state.

### 3) Dependencies
- Milestone 1 completion (already achieved):
  - FastAPI app scaffold, async SQLAlchemy DB layer, Alembic setup, tests foundation
  - existing `conversation_grades` model + migration baseline
- Documentation inputs:
  - `docs/milestone-2/milestone-2.md`
  - `docs/milestone-2/milestone-notes.md`
  - `docs/milestone-2/SRS_Phase2_1pager.docx`
  - `docs/milestone-2/SRS_Phase2_FeatureChanges.docx`
  - `docs/milestone-2/SRS_Phase2_MetricsGuide.docx`
- Runtime tooling:
  - Alembic / SQLAlchemy available in the project environment
- Phase 1 should not depend on AI provider credentials or batch execution infrastructure (those are Phase 3+ concerns).

### 4) Configuration
- Phase 1 should define the configuration contract for downstream phases, even if not fully consumed yet:
  - highlight rule defaults (stored in DB config table; exact seed values start from current SRS defaults)
  - auth-related settings placeholders (password hashing config + auth secret/expiry settings, transport details finalized in Phase 2)
- If phase work introduces constants/maps (intent taxonomy, identity type enum values), prefer centralized modules over duplicated literals.
- Configuration that controls runtime auth behavior should be minimal in Phase 1 unless required by schema decisions.

### 5) Endpoints
- Phase 1 is primarily schema/data-contract work and does **not** need to ship Milestone 2 feature endpoints.
- Optional/acceptable endpoint impact in this phase:
  - no-op (none), or
  - placeholder schemas/constants imported by future route modules
- Auth endpoints, metrics endpoints, and monitoring endpoints are explicitly deferred to later phases.

## Dependencies
- Phase dependency: `Milestone 1 complete -> Milestone 2 Phase 1`
- Downstream phase impact:
  - Phase 2 (Auth + Accounts Foundation) depends on Phase 1 auth/account/profile schema contract
  - Phase 3 (AI Grading Pipeline Core) depends on Phase 1 grading/intent/highlight config schema contract
  - Phase 5/6 API phases depend on Phase 1 indexes/contracts for query design

## Gate 1.0 - Shared Milestone 2 Data Contracts

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| 1.0.1 | `P2.1.1 - Design - Finalize customer-day grade grain and canonical identity contract - Gate (Independent)` | Design | None | Documented grade grain + canonical identity rules + compatibility notes |
| 1.0.2 | `P2.1.2 - Design - Finalize intent taxonomy codes/labels map for Milestone 2 - Gate (Dependent)` | Design | `P2.1.1` | Canonical `intent_code` / `intent_label` mapping and normalization rules |
| 1.0.3 | `P2.1.3 - Design - Define configurable highlight-rules data contract and compute-on-read policy - Gate (Dependent)` | Design | `P2.1.1` | Highlight config table contract + service-layer computation policy |
| 1.0.4 | `P2.1.4 - Design - Define auth account/profile schema contract and security constraints - Gate (Dependent)` | Design | `P2.1.1` | Auth/account/profile model decisions and unresolved auth-specific assumptions list |

### Gate 1.0 Scope (P2.1.1 - P2.1.4)
- Lock the customer-day grade grain used by Milestone 2 monitoring and grading.
- Finalize canonical identity fields and source/type semantics for `conversation_grades`.
- Confirm `intent_code` as authoritative and define backend taxonomy mapping.
- Define highlight configuration storage approach (config table) while preserving compute-on-read behavior.
- Define auth/account/profile schema scope sufficient for migration work (without requiring full auth endpoint design).

### Suggested Files for Gate 1.0
- `docs/milestone-2/m2-phase-1.md` (this plan; update as decisions close)
- `app/models/conversation_grades.py`
- `app/models/` (new auth/profile/highlight config models)
- `app/models/enums.py` or a new constants/taxonomy module (if expanded)

### Gate 1.0 Acceptance Criteria
- [x] Customer-day grade grain is explicit and consistent with Milestone 2 monitoring direction.
- [x] Canonical identity contract is defined without requiring raw chat table modifications.
- [x] Intent taxonomy normalization rules and storage fields (`intent_code`, `intent_label`) are documented.
- [x] Highlight rules configuration is defined as DB-backed and highlights remain computed on read.
- [x] Auth/account/profile schema scope is sufficiently defined for migration implementation, with open auth mechanism questions clearly listed.

### P2.1.1 Decision Record - Customer-Day Grade Grain and Canonical Identity Contract

#### Decision Summary
- Milestone 2 grading and monitoring use a **customer-day** grain: one grade row per canonical customer identity per business day.
- Business day is anchored to **Gulf Standard Time (`Asia/Dubai`)** for grouping and `grade_date`.
- Raw chat/source tables remain unchanged; grade-to-message association is derived using canonical identity + GST day.

#### Customer-Day Grade Grain (Canonical)
- Canonical grain key target (business key direction):
  - `identity_type + conversation_identity + grade_date`
- `grade_date` semantics:
  - Date derived from chat timestamps converted to `Asia/Dubai`
  - Represents the GST day window `[00:00, 24:00)` for the graded conversation-day
- One grade row aggregates all messages for the resolved canonical identity within that GST day.
- This intentionally collapses multiple same-day interactions for the same identity into one grade row (consistent with current Phase 2 scope and the "multi-conversation-per-day handling" out-of-scope note).
- Cross-day history remains a sequence of customer-day rows and is used by the future grade history timeline.

#### Canonical Identity Resolution Rules (for raw chats -> customer-day grouping)
- Source fields (in priority order):
  1. `customer_phone`
  2. `customer_email_address`
  3. `session_id`
- Canonical identity selection rule:
  - Use the first non-null, non-blank value from the priority order above after trim normalization.
- `identity_type` canonical values for Milestone 2 Phase 1:
  - `phone`
  - `email`
  - `session`
- `conversation_identity` stores the selected normalized value (string) associated with `identity_type`.
- Channel is **not** part of the canonical identity key.
- If a person appears under different identifiers with no deterministic bridge (for example, separate phone and email records), they remain separate canonical identities in Milestone 2 v1.
- Rows with no usable identity (`phone/email/session` all null/blank) are not gradeable under the customer-day contract and should be excluded from grading/monitoring derivation (documented limitation; no synthetic key introduced in Phase 1).

#### `conversation_grades` Compatibility and Migration Notes
- Existing Milestone 1 `conversation_grades` rows are keyed by `phone_number + grade_date`.
- Phase 1 migration should be additive and transition-safe:
  - Add canonical identity fields (for example `identity_type`, `conversation_identity`) without changing raw chat tables
  - Preserve existing `phone_number` during transition for backward compatibility
  - Backfill canonical identity fields from `phone_number` for legacy rows where possible (`identity_type = phone`)
- Read/query logic in transitional phases should prefer canonical identity fields when present and fall back to legacy `phone_number` semantics where required.
- Unique/constraint migration strategy should avoid breaking existing data:
  - Add canonical columns and supporting indexes first
  - Introduce stricter uniqueness/NOT NULL constraints only after backfill safety is verified
- No foreign key from raw chat rows to `conversation_grades` is introduced in Phase 1.

#### Monitoring and API Contract Implications (for downstream phases)
- Customer-day monitoring list and detail APIs should use the same canonical identity resolution rules as grading.
- Full conversation view (across time) remains a separate endpoint surface and should not change the Phase 1 customer-day grain contract.
- Shared constants for identity-type values should be centralized in a later Phase 1 task (`P2.1.14`) after Gate decisions are finalized.

### P2.1.2 Decision Record - Intent Taxonomy Codes/Labels and Normalization Contract

#### Decision Summary
- Milestone 2 uses canonical `intent_code` values (authoritative) with paired `intent_label` values (display).
- `intent_reasoning` remains required at grading time and should be stored in English per SRS guidance.
- The SRS category lists currently enumerate 15 business labels while describing a fixed 16-label taxonomy; this phase resolves the mismatch by adding a system fallback intent: `unknown`.

#### Canonical Taxonomy (v1)

| Category | intent_code | intent_label |
|---|---|---|
| Policy Related | `policy_inquiry` | `Policy Inquiry` |
| Policy Related | `policy_purchase` | `Policy Purchase` |
| Policy Related | `policy_modification` | `Policy Modification` |
| Policy Related | `policy_cancellation` | `Policy Cancellation` |
| Claims Related | `claims_submission` | `Claims Submission` |
| Claims Related | `claims_follow_up` | `Claims Follow-up` |
| Claims Related | `claims_dispute` | `Claims Dispute` |
| Billing & Payments | `payment_inquiry` | `Payment Inquiry` |
| Billing & Payments | `payment_issue` | `Payment Issue` |
| Documents & Admin | `document_request` | `Document Request` |
| Documents & Admin | `account_profile_update` | `Account / Profile Update` |
| Support & Complaints | `general_inquiry` | `General Inquiry` |
| Support & Complaints | `complaint` | `Complaint` |
| Support & Complaints | `escalation_request` | `Escalation Request` |
| Non-genuine | `wasteful` | `Wasteful` |
| System Fallback | `unknown` | `Unknown` |

#### Normalization Rules (Legacy/Source Labels -> Canonical Code)
- Normalize input labels with:
  - trim leading/trailing whitespace
  - collapse internal repeated whitespace
  - case-insensitive comparison
- Canonical mapping examples for legacy/source values:
  - `New Get-A-Quote Form Submitted in UAE` -> `policy_purchase`
  - `New Contact Form Submitted` -> `general_inquiry`
  - `Policy Inquiry` -> `policy_inquiry`
  - `Claims Status` -> `claims_follow_up`
  - `Renewal` -> `policy_modification`
  - `Technical Support` -> `general_inquiry`
  - `Agent Needs Assistance` -> `escalation_request`
  - `Greeting` / `Farewell` / `Goodbye` -> `unknown`
- Null/blank/unmapped labels resolve to `unknown`.
- During migration/backfill, preserve raw legacy label evidence in `intent_label` when useful for auditability, but ensure `intent_code` is populated from this mapping contract.

#### Storage/Constraint Implications (for Streams A and D)
- `intent_code` is the filtering/index key for metrics/monitoring and should become non-null after transition-safe backfill.
- `intent_label` is response-facing text and should default to the canonical label for the chosen `intent_code`.
- Shared code constants/enums for these 16 `intent_code` values are deferred to `P2.1.14` but this decision record is now the canonical source of truth.

### P2.1.3 Decision Record - Highlight Rules Config Contract and Compute-on-Read Policy

#### Decision Summary
- Highlight indicators remain computed on read in monitoring services; they are not persisted on `conversation_grades`.
- A DB-backed configuration table is introduced in Phase 1 to hold adjustable threshold/toggle values for highlight logic.
- Phase 1 uses a single active config row model (no full version history table yet); future versioning is explicitly deferred.

#### Highlight Config Table Contract (Phase 1)
- Proposed table name: `monitoring_highlight_config`
- Row model: singleton active row in v1 (`id = 1` convention or unique `is_active = true` constraint)
- Columns:
  - `id` (primary key)
  - `is_active` (`bool`, default `true`)
  - `frustration_min_threshold` (`smallint`, default `7`)
  - `failure_escalation_enabled` (`bool`, default `true`)
  - `loop_detected_enabled` (`bool`, default `true`)
  - `accuracy_max_threshold` (`smallint`, default `3`)
  - `unresolved_low_satisfaction_enabled` (`bool`, default `true`)
  - `unresolved_satisfaction_max_threshold` (`smallint`, default `3`)
  - `user_irrelevancy_enabled` (`bool`, default `true`)
  - `updated_at` (`timestamp`, auto-updated)
- Constraint guidance:
  - numeric thresholds constrained to score domain `1..10`
  - exactly one active config row in v1 (enforced by app logic or unique partial index)

#### Default Rule Set (Seeded in Phase 1 Migration)
- `frustration_high`: trigger when `frustration_score >= frustration_min_threshold` (default `7`)
- `escalation_failure`: trigger when `escalation_type = 'failure'` and toggle enabled
- `loop_detected`: trigger when `loop_detected = true` and toggle enabled
- `accuracy_low`: trigger when `accuracy_score <= accuracy_max_threshold` (default `3`)
- `unresolved_low_satisfaction`: trigger when `resolution = false` and `satisfaction_score <= unresolved_satisfaction_max_threshold` (default `3`) and toggle enabled
- `user_irrelevancy`: trigger when `user_relevancy = false` and toggle enabled

#### Compute-on-Read Policy (Service Layer)
- Monitoring list/detail responses evaluate highlights at read time using:
  - the grade row fields
  - the single active `monitoring_highlight_config` row
- Response contract returns:
  - zero or more triggered highlight codes
  - response-facing labels (finalized in `P2.1.10`)
- No highlight state is written back to grade rows.
- If config cannot be loaded, service falls back to seeded defaults and records operational warning logs.

#### Migration/Operational Implications
- Migration in Stream B adds the config table additively and seeds a default active row.
- Historical responses reflect current config (not historical config-at-time) in Phase 1/Phase 2 scope.
- Future phase may add versioned rule sets, but this phase intentionally keeps schema simple for downstream delivery.

### P2.1.4 Decision Record - Auth Account/Profile Schema Contract and Security Constraints

#### Decision Summary
- Phase 1 introduces a single `accounts` persistence model for auth + minimal profile data.
- Login identifier is `email` (normalized), with password-hash-only storage.
- Roles are fixed to `super_admin`, `company_admin`, and `analyst` in Phase 1.
- Auth transport remains an implementation concern for Phase 2; Phase 1 does not require token/session tables.

#### Account Schema Contract (Phase 1)
- Proposed table name: `accounts`
- Required columns:
  - `id` (`uuid` primary key)
  - `email` (`varchar(320)`, not null)
  - `password_hash` (`varchar(255)`, not null)
  - `full_name` (`varchar(150)`, not null)
  - `role` (`enum`: `super_admin`, `company_admin`, `analyst`; not null)
  - `is_active` (`bool`, not null, default `true`)
  - `last_login_at` (`timestamp`, nullable)
  - `created_at` (`timestamp`, not null, default now)
  - `updated_at` (`timestamp`, not null, default now, auto-updated)

#### Constraint and Index Contract
- Email uniqueness:
  - enforce case-insensitive uniqueness via a unique index on normalized/lower email
  - persist email in normalized form (`trim` + lowercase)
- Role constraint:
  - DB enum/check must reject values outside `super_admin`, `company_admin`, `analyst`
- Password hash constraint:
  - non-empty and sufficiently long hash string; plaintext password is never persisted
- Optional safety constraints:
  - prevent zero-length `full_name` after trimming
  - keep `is_active` true by default for new accounts unless explicitly disabled

#### Security Constraints (Phase 1 Scope)
- Password handling:
  - application stores only secure password hashes (Argon2id or bcrypt acceptable in Phase 2 implementation)
  - never log raw passwords or derived secret material
- Account enumeration and brute-force protections are implementation concerns for Phase 2 auth endpoints; no schema additions are required in Phase 1.
- No reset/change password tables in Phase 1.
- No tenant/company linkage table is required for `company_admin` in Milestone 2 v1.

#### Auth Mechanism Clarification (Bounded for Phase 1)
- Phase 1 schema is transport-agnostic and does not require stateful session storage.
- Phase 2 may implement JWT bearer auth without additional auth tables.
- If Phase 2 later chooses server-side sessions, required session persistence can be added as a separate additive migration.

### P2.1.10 Decision Record - Shared Highlight Codes and Response-Facing Labels Contract

#### Decision Summary
- Highlight triggers use a fixed canonical code set (stable API contract) with paired response-facing labels.
- Code values are lowercase `snake_case` and must be treated as the authoritative machine contract.
- Label values are human-readable display strings intended for monitoring list/detail UI badges.
- Shared constants are centralized in `app/core/constants.py` to avoid duplicated literals in future monitoring APIs.

#### Canonical Highlight Contract (Phase 1)

| highlight_code | label | Trigger Source |
|---|---|---|
| `frustration_high` | `High Frustration` | `frustration_score >= frustration_min_threshold` |
| `escalation_failure` | `Failed Escalation` | `escalation_type = failure` and toggle enabled |
| `loop_detected` | `Conversation Loop` | `loop_detected = true` and toggle enabled |
| `accuracy_low` | `Low Accuracy` | `accuracy_score <= accuracy_max_threshold` |
| `unresolved_low_satisfaction` | `Unresolved + Low Satisfaction` | `resolution = false` and `satisfaction_score <= unresolved_satisfaction_max_threshold` and toggle enabled |
| `user_irrelevancy` | `Non-genuine Interaction` | `user_relevancy = false` and toggle enabled |

#### Shared Constants Contract
- `HIGHLIGHT_CODE_TO_LABEL`: canonical map of code -> label.
- `HIGHLIGHT_CODES`: tuple of canonical highlight codes (derived from the map keys).
- Import path for downstream phases: `from app.core import HIGHLIGHT_CODES, HIGHLIGHT_CODE_TO_LABEL`.

## Stream A - `conversation_grades` Contract + ORM Updates

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| A.1 | `P2.1.5 - DB - Update conversation_grades ORM model for Milestone 2 fields - Stream A (Dependent)` | DB | `P2.1.4` | ORM model changes for canonical identity and intent normalization support |
| A.2 | `P2.1.6 - DB - Add Alembic migration for conversation_grades Milestone 2 contract changes - Stream A (Dependent)` | DB | `P2.1.5` | Additive migration with indexes/constraints/backfill-safe steps |
| A.3 | `P2.1.7 - QA - Validate conversation_grades migration upgrade/downgrade behavior - Stream A (Dependent)` | QA | `P2.1.6` | Migration verification notes and safe rollback validation |

### Stream A Implementation Notes
- Prefer additive schema changes and transition-safe constraints.
- Keep existing Milestone 1 data readable during migration transition.
- Indexes should reflect downstream query needs (monitoring filters/sorts) without over-indexing prematurely.

### Suggested Files (Stream A)
- `app/models/conversation_grades.py`
- `alembic/versions/*.py`
- `app/models/enums.py` or `app/core/constants.py` (if taxonomy/identity enums are centralized)

### Stream A Acceptance Criteria
- [ ] `conversation_grades` supports canonical identity fields and `intent_code`.
- [ ] Migration is additive-only and does not alter raw chat/source tables.
- [ ] Rollback path is verified for the new revision(s).

## Stream B - Highlight Rules Configuration Schema

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| B.1 | `P2.1.8 - DB - Add highlight rules configuration ORM model - Stream B (Dependent)` | DB | `P2.1.3` | ORM model for configurable highlight thresholds/rules |
| B.2 | `P2.1.9 - DB - Add Alembic migration and default seed strategy for highlight rules config - Stream B (Dependent)` | DB | `P2.1.8` | Config table migration with initial defaults contract |
| B.3 | `P2.1.10 - Design - Define shared highlight codes and response-facing labels contract - Stream B (Dependent)` | Design | `P2.1.3` | Canonical highlight code set for later monitoring APIs |

### Stream B Implementation Notes
- Phase 1 stores configuration only; highlights remain computed in read services in Phase 6.
- Prefer a strongly-typed table schema over key-value/EAV for v1.
- Versioning/active-ruleset selection may be deferred, but the migration should not block future versioning.

### Suggested Files (Stream B)
- `app/models/` (new highlight config model)
- `alembic/versions/*.py`
- `app/core/constants.py` or `app/services/monitoring_highlights.py` (shared code constants placeholder)

### Stream B Acceptance Criteria
- [ ] Highlight config table contract exists and supports configurable thresholds/toggles.
- [ ] Initial/default rule values are defined (even if exact values remain adjustable later).
- [ ] Shared highlight codes are documented for Phase 6 API work.

## Stream C - Auth and Account Data Model + Migration

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| C.1 | `P2.1.11 - DB - Add account ORM model (auth + minimal profile columns) - Stream C (Dependent)` | DB | `P2.1.4` | SQLAlchemy account model with email, password hash, full name, and role fields |
| C.2 | `P2.1.12 - DB - Add Alembic migration for account table and role constraints/indexes - Stream C (Dependent)` | DB | `P2.1.11` | Additive account/auth schema migration |
| C.3 | `P2.1.13 - QA - Validate account migration constraints and uniqueness rules - Stream C (Dependent)` | QA | `P2.1.12` | Migration verification notes for account/auth schema |

### Stream C Implementation Notes
- Phase 1 is schema-only for auth/accounts; endpoint behavior is Phase 2.
- Use a single account table for v1 (auth + minimal profile columns, including `full_name`).
- Do not add reset/change-password workflow tables in Phase 1.
- Auth mechanism specifics should not force unnecessary tables yet unless Phase 2 selects a design that requires them.
- Keep the schema minimal and extensible.

### Suggested Files (Stream C)
- `app/models/` (new account model)
- `alembic/versions/*.py`
- `app/db/base.py` / `app/models/__init__.py` (if imports/metadata wiring changes)

### Stream C Acceptance Criteria
- [ ] Account ORM model follows SQLAlchemy 2.0 declarative style.
- [ ] Passwords are stored as hashes (schema/field naming makes plaintext storage non-default).
- [ ] Account migration is additive and reversible.
- [ ] Uniqueness/index constraints align with `email` login contract.
- [ ] Role values support `super_admin`, `company_admin`, and `analyst`.

## Stream D - Shared Contracts and Phase Validation

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| D.1 | `P2.1.14 - API - Define shared schema/constants contracts for downstream Milestone 2 phases - Stream D (Dependent)` | API | `P2.1.2`, `P2.1.3`, `P2.1.4` | Centralized intent/highlight/identity/auth schema primitives or constants |
| D.2 | `P2.1.15 - QA - Run compile and migration smoke checks for Phase 1 changes - Stream D (Dependent)` | QA | `P2.1.7`, `P2.1.9`, `P2.1.13`, `P2.1.14` | Phase 1 verification baseline for downstream execution |

### Stream D Implementation Notes
- This stream is the handoff bridge to Phase 2 and Phase 3.
- Focus on removing ambiguity in shared contract constants and documenting assumptions for later endpoint phases.

### Suggested Files (Stream D)
- `app/schemas/` (if shared schema primitives are introduced)
- `app/core/` or `app/models/enums.py` (constants/taxonomies)
- `docs/tasks.md` (future checklist updates after task finalization)

### Stream D Acceptance Criteria
- [ ] Downstream phases can import centralized intent/highlight/identity constants without duplicating literals.
- [ ] Phase 1 code compiles cleanly.
- [ ] Migration smoke checks pass against Milestone 1 baseline state.

## Component Dependency Summary
- `conversation_grades` contract changes (Stream A) depend on Gate 1.0 identity + intent decisions.
- Highlight config schema (Stream B) depends on Gate 1.0 highlight config contract decisions.
- Auth/profile schema (Stream C) depends on Gate 1.0 auth/profile contract decisions.
- Shared contracts and final validation (Stream D) depend on outputs from Streams A/B/C.
- Phase 2 and Phase 3 should not start implementation until Stream D completes.

## Parallelization Map

```text
Gate 1.0 (P2.1.1 - P2.1.4 Shared Data Contracts) --------------------+
                                                                      |
  |- Stream A (conversation_grades contract + migration) -----------> |
  |- Stream B (highlight rules config schema) ----------------------> |  (parallel after Gate)
  |- Stream C (auth/profile models + migration) --------------------> |
                                                                      |
  |- Stream D (shared contracts + phase validation) ----------------> |  (after A/B/C)
                                                                      v
                    Phase 1 Complete (Milestone 2 Data Contract + Migrations)
```

## Definition of Done (Phase 1)
- [ ] Gate 1.0 decisions are implemented or explicitly documented with bounded deferrals.
- [ ] `conversation_grades` Milestone 2 data contract changes are migrated additively.
- [ ] Highlight-rules configuration schema exists and is ready for read-time highlight computation in Phase 6.
- [ ] Auth/account/profile schema exists and is ready for Phase 2 auth implementation.
- [ ] Shared constants/contracts for intent/highlight/identity are centralized for downstream phases.
- [ ] Phase 1 migrations and compile checks pass without modifying raw chat/source tables.
- [ ] No lint/syntax errors in modified Python modules.

## Test Scenarios (Phase 1 Validation)

### Happy Path
- Alembic upgrade from Milestone 1 latest revision applies cleanly to add Phase 1 schema changes
- Alembic downgrade of Phase 1 revision(s) succeeds
- ORM metadata imports resolve cleanly after adding new models
- Default highlight config row/table can be queried after migration

### Edge Cases
- Existing `conversation_grades` rows without new canonical identity fields are handled by transition-safe migration steps
- Legacy rows with `intent_label` values that do not map cleanly to canonical `intent_code` remain migration-safe (documented fallback)
- Auth/profile uniqueness constraints behave correctly for duplicate login identifiers
- Empty or missing optional profile fields do not violate schema constraints

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- Highlights remain computed on read and are not persisted on `conversation_grades` rows in Milestone 2 v1.
- A DB-backed highlight rules configuration table is included in Phase 1.
- Raw chats/source tables remain unchanged for Milestone 2 linkage.
- Phase 1 does not ship auth endpoints; it prepares auth/account/profile schema only.
- Auth login uses `email + password` with password-hash storage only.
- Account/profile data is stored in a single account table for Milestone 2 v1 with minimal profile fields (at minimum `full_name`).
- Roles include `super_admin`, `company_admin`, and `analyst`.
- Milestone 2 auth scope is login-only (password reset/change deferred).
- `company_admin` does not require explicit company/tenant linkage in the Phase 1 schema for Milestone 2 v1.

### Auth/Profile Clarifications Needed (Recommended Before Phase 1 Execution)
- None blocking for Phase 1 schema execution. Transport choice remains bounded to Phase 2 implementation and does not block Phase 1 migrations.

### Other Open Questions
- Taxonomy count mismatch was resolved in `P2.1.2` by introducing canonical system fallback code `unknown` as the 16th label.
- Highlight config versioning is deferred beyond Phase 1 (single active config row in v1).

## Estimated Duration (Units)
- Gate 1.0 (`P2.1.1` - `P2.1.4`): `2.0`
- Stream A (`P2.1.5` - `P2.1.7`): `2.25`
- Stream B (`P2.1.8` - `P2.1.10`): `1.75`
- Stream C (`P2.1.11` - `P2.1.13`): `2.0`
- Stream D (`P2.1.14` - `P2.1.15`): `1.0`
- Sequential total: `9.0`
- Parallelized total after Gate (A/B/C concurrent, then D): `~5.0 - 5.75` plus Gate

## Done Condition for Phase 1 Planning
Phase 1 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-1.md`)
- Gate/stream tasks are clear enough to execute one atomic task at a time
- Auth/profile open questions are either answered or explicitly accepted as bounded assumptions
- Migration scope is additive-only and does not conflict with Milestone 1 data safety constraints
