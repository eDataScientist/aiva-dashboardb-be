# Milestone 2 - Phase 2 Plan: Auth and Accounts Foundation

## Goals
- Deliver a simple, maintainable password-auth foundation for Milestone 2 protected APIs.
- Implement authenticated account profile read/update endpoints for the logged-in account.
- Introduce shared auth guards/dependencies that downstream Milestone 2 routes can reuse.
- Preserve additive-only schema behavior (no destructive migration work on existing tables).
- Leave Phase 2 in a reviewable state with focused auth/profile test coverage.

## Planning Analysis (Required Order)

### 1) Data Models
- Phase 1 already introduced `accounts` with core auth fields (`email`, `password_hash`, `full_name`, `role`, `is_active`, `last_login_at`).
- Phase 2 should add runtime contracts (Pydantic/service-level) for:
  - login request + token response
  - authenticated account context (`/auth/me`)
  - profile patch payload for self-service updates
- Role contract stays: `super_admin`, `company_admin`, `analyst`.
- Access model is baseline-only in this phase: auth-required routes plus bounded role checks where necessary.

### 2) Migration
- Default path: no mandatory new tables are expected for Phase 2.
- A dedicated gate task verifies whether schema gaps exist for auth/profile behavior.
- If gaps are found, only additive migration changes are allowed (no destructive edits, no legacy table rewrites).
- Any migration introduced in this phase must include upgrade/downgrade verification.

### 3) Dependencies
- Upstream dependency satisfied: Milestone 2 Phase 1 is complete (`accounts` table + role constraints/indexes already in place).
- Existing async DB/session and router scaffolding are ready (`app/db/*`, `app/api/router.py`).
- Phase 2 should not depend on grading/batch infrastructure (Phase 3+ scope).
- Test foundation exists and should be extended with auth/profile suites.

### 4) Configuration
- Add explicit auth settings to app config (JWT secret, algorithm, token expiry, optional issuer/audience, hash policy).
- Ensure missing/weak auth configuration fails early in startup/config validation.
- Keep defaults safe and explicit; avoid hidden insecure fallbacks.
- Centralize auth constants to prevent literal drift across routes/services/tests.

### 5) Endpoints
- `POST /api/v1/auth/login` - email/password authentication and bearer token issuance.
- `GET /api/v1/auth/me` - return authenticated account identity/profile snapshot.
- `GET /api/v1/accounts/me` - fetch current account profile.
- `PATCH /api/v1/accounts/me` - update allowed self-profile fields (`full_name` in Phase 2 baseline).
- Apply auth guard policy to protected route groups and register public auth endpoints.

## Dependencies
- Phase dependency: `Milestone 2 Phase 1 complete -> Milestone 2 Phase 2`.
- Downstream phase impact:
  - Phase 3+ can rely on shared auth dependency for protected grading/monitoring APIs.
  - Phase 6 monitoring endpoints should reuse this phase's auth guard and role baseline.

## Gate 2.0 - Auth Core Contract and Security Primitives

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| 2.0.1 | `P2.2.1 - Design - Finalize auth transport, token claims, and route access matrix - Gate (Independent)` | Lock Phase 2 auth decisions (JWT bearer baseline), claim set, and protected/public route matrix. | None | `docs/milestone-2/m2-phase-2.md`, `docs/milestone-2/milestone-notes.md` (if decision updates needed) | Review checklist confirms route access and claim contract are explicit and unambiguous. |
| 2.0.2 | `P2.2.2 - DB - Validate account schema readiness and add additive migration if gaps exist - Gate (Dependent)` | Confirm `accounts` schema is sufficient; if not, add bounded additive migration only. | `P2.2.1` | `alembic/versions/*.py` (only if required), `app/models/account.py` (only if required) | Alembic upgrade/downgrade smoke for any new revision; no destructive changes. |
| 2.0.3 | `P2.2.3 - Config - Add auth settings contract and validation rules - Gate (Dependent)` | Introduce and validate required auth settings (secret, algorithm, expiry). | `P2.2.1` | `app/core/config.py`, `app/core/__init__.py`, `.env.example` (if present) | Compile check and config validation checks for missing/invalid auth settings. |
| 2.0.4 | `P2.2.4 - API - Define auth and account profile schemas plus auth error payloads - Gate (Dependent)` | Add typed request/response models for login, token responses, `/auth/me`, and `/accounts/me` patch. | `P2.2.1` | `app/schemas/auth.py` (new), `app/schemas/accounts.py` (new), `app/schemas/__init__.py` | Schema import/OpenAPI smoke check and validation tests for payload constraints. |
| 2.0.5 | `P2.2.5 - Service - Implement password hashing/token utilities and current-account dependency primitives - Gate (Dependent)` | Deliver reusable security primitives (hash, verify, token create/decode) and base current-account dependency wiring. | `P2.2.2`, `P2.2.3`, `P2.2.4` | `app/core/security.py` (new), `app/db/deps.py` or `app/api/deps/auth.py` (new), `app/core/constants.py` | Unit tests for token/credential utilities and invalid-token paths. |

### P2.2.1 Decision Record (Finalized `2026-03-05`)

#### Auth Transport Contract
- Transport: JWT bearer token via `Authorization: Bearer <token>`.
- Login response contract (Phase 2): `access_token`, `token_type` (`bearer`), `expires_in_seconds`.
- Token classes: access token only in Phase 2 (`refresh` and rotation are out of scope).
- Signing baseline: symmetric JWT signing with algorithm from config (`HS256` default in config task).
- Secret policy: signing secret must come from environment/config; no implicit insecure fallback.

#### Token Claim Contract
- Required claims:
  - `sub`: account identifier as string (UUID text from `accounts.id`)
  - `email`: normalized lowercase account email
  - `role`: one of `super_admin`, `company_admin`, `analyst`
  - `type`: `access`
  - `iat`: issued-at timestamp
  - `exp`: expiration timestamp
- Optional claims (included only when configured): `iss`, `aud`.
- Validation baseline:
  - reject tokens with invalid signature, wrong/missing required claims, unsupported `type`, or expiration.
  - current-account dependency must still load account row and fail auth for missing/inactive account records.

#### Route Access Matrix (Phase 2 Baseline)

| Route Surface | Access Level | Role Policy (Phase 2) | Notes |
|---|---|---|---|
| `POST /api/v1/auth/login` | Public | N/A | Credential exchange endpoint; no prior auth required. |
| `GET /api/v1/auth/me` | Authenticated | Any active role | Returns token-resolved current account context. |
| `GET /api/v1/accounts/me` | Authenticated | Any active role | Self profile read endpoint. |
| `PATCH /api/v1/accounts/me` | Authenticated | Any active role | Self profile update endpoint (`full_name` baseline scope). |
| `/api/v1/analytics/*` | Authenticated | Any active role | Authentication required in Phase 2; fine-grained role restrictions deferred. |
| `/api/v1/conversations/*` | Authenticated | Any active role | Authentication required in Phase 2; fine-grained role restrictions deferred. |
| `GET /health` | Public | N/A | Operational health probe remains unauthenticated. |

#### Deferred Items
- Fine-grained role restrictions (beyond auth-required baseline for analytics/conversations) are deferred to later Milestone 2 phases and detailed in `P2.2.13`.
- Refresh-token lifecycle, logout invalidation, and password reset/change flows remain out of scope for Phase 2.

### P2.2.2 Schema Readiness Validation (Completed `2026-03-05`)

#### Validation Scope
- Target model: `accounts`
- Target artifacts reviewed:
  - `app/models/account.py`
  - `alembic/versions/c3a1f82d9b55_add_accounts_table.py`
- Phase 2 contract inputs:
  - `P2.2.1` auth transport and token claims contract
  - Phase 2 endpoint scope (`/auth/login`, `/auth/me`, `/accounts/me`)

#### Requirement-to-Schema Check
- Authentication identity:
  - `email` present, required, normalized at ORM layer, case-insensitive unique index (`uq_accounts_email_lower`) present.
- Credential verification:
  - `password_hash` present, required, non-empty constraint present.
- Authorization context:
  - `role` present with DB check constraint restricting values to `super_admin`, `company_admin`, `analyst`.
  - `is_active` present and required with default `true`.
- Auth/session metadata:
  - `last_login_at` present for successful-login timestamp updates.
- Profile baseline:
  - `full_name` present, required, non-empty constraint present.
- Token subject compatibility:
  - UUID primary key `id` present and suitable for JWT `sub`.

#### Outcome
- No schema gaps were identified for Phase 2 auth/profile baseline behavior.
- No additive migration is required in `P2.2.2`.
- If future requirements add refresh-token tracking, password-reset audit, or tenant linkage, those should be handled in later additive migrations.

### P2.2.3 Auth Settings Contract (Completed `2026-03-05`)

#### Required Runtime Settings
- `AUTH_JWT_SECRET`: signing secret for JWT access tokens (minimum 32 characters).
- `AUTH_JWT_ALGORITHM`: must be one of `HS256`, `HS384`, `HS512`.
- `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`: positive integer token TTL, bounded to `<= 1440`.

#### Optional Runtime Settings
- `AUTH_JWT_ISSUER`: optional `iss` claim value when non-empty.
- `AUTH_JWT_AUDIENCE`: optional `aud` claim value when non-empty.

#### Validation and Failure Behavior
- Settings validation now fails fast for:
  - missing/short JWT secret
  - unsupported JWT algorithm
  - invalid token expiry values
- Application settings bootstrap error message now explicitly references auth settings contract failures.
- Test bootstrap (`tests/conftest.py`) now sets deterministic auth env defaults so app import is stable during test initialization.

### P2.2.4 Auth and Account Schema Contract (Completed `2026-03-05`)

#### Created Schema Modules
- `app/schemas/auth.py`
  - `LoginRequest`
  - `TokenResponse`
  - `LoginResponse`
  - `AuthMeResponse`
  - `TokenClaims`
  - `AuthErrorCode` / `AuthErrorResponse`
- `app/schemas/accounts.py`
  - `AccountRoleSchema`
  - `AccountContext`
  - `AccountMeResponse`
  - `AccountProfilePatchRequest`
  - `AccountProfilePatchResponse`

#### Contract Outcomes
- Login payload contract includes normalized email and non-blank password validation.
- Auth token response contract is explicit (`access_token`, `token_type=bearer`, `expires_in_seconds`).
- Current-account response contracts are reusable across `/auth/me` and `/accounts/me`.
- Self-profile patch contract is constrained to validated `full_name` updates.
- Stable auth error payload schema is defined for unauthorized/invalid-credential/token paths.

#### Validation Evidence
- Schema constraint tests added: `tests/test_auth_schemas.py`.
- OpenAPI/schema import smoke check succeeds with auth settings env present.

### P2.2.5 Security Primitives and Current-Account Dependency (Completed `2026-03-05`)

#### Implemented Security Utilities
- `app/core/security.py` now provides:
  - password hashing (`hash_password`) with PBKDF2-SHA256 + per-hash salt
  - password verification (`verify_password`)
  - JWT access token creation (`create_access_token`)
  - JWT access token decode/validation (`decode_access_token`)
  - token response helper (`build_access_token_response`)
- Auth constants were centralized in `app/core/constants.py` for token type/scheme/hash parameters.

#### Implemented Auth Dependencies
- Added `app/api/deps/auth.py`:
  - `get_token_claims` for bearer extraction + JWT decode + auth error mapping.
  - `get_current_account` for token subject resolution and active-account enforcement.
- Added `app/api/deps/__init__.py` exports for dependency reuse in routes.

#### Validation Evidence
- New security utility tests: `tests/test_security.py`.
- Targeted auth schema + security test run passed:
  - `pytest tests/test_auth_schemas.py tests/test_security.py -q` -> `10 passed`.
- Compile check passed:
  - `python -m compileall app/`.

### Gate 2.0 Acceptance Criteria
- [x] Auth transport and route access matrix are finalized and documented.
- [x] Any schema delta is additive-only and migration-safe.
- [x] Auth configuration contract is validated at startup/config load.
- [x] Shared security primitives and current-account dependency are ready for route use.
- [x] Auth/profile schemas are complete enough to implement Streams A/B/C without contract rework.

## Stream A - Authentication Endpoints

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| A.1 | `P2.2.6 - Service - Implement account authentication flow with active-account checks - Stream A (Dependent)` | Authenticate by normalized email + password hash verification and enforce `is_active` guard; update `last_login_at` on success. | `P2.2.5` | `app/services/auth.py` (new), `app/models/account.py` (if minor helper updates) | Service-layer tests for valid creds, wrong password, unknown user, inactive user. |
| A.2 | `P2.2.7 - API - Add login endpoint issuing access tokens and account context - Stream A (Dependent)` | Implement `POST /api/v1/auth/login` with stable success/error contract and token issuance. | `P2.2.6` | `app/api/routes/auth.py` (new), `app/api/router.py` | Route tests for 200/401/422 and OpenAPI schema presence. |
| A.3 | `P2.2.8 - API - Add authenticated identity endpoint for current account context - Stream A (Dependent)` | Implement `GET /api/v1/auth/me` using shared current-account dependency. | `P2.2.7` | `app/api/routes/auth.py`, auth dependency module from Gate | Route tests for 200, missing token (401), invalid token (401). |
| A.4 | `P2.2.9 - Test - Add auth service and route tests for success and failure paths - Stream A (Dependent)` | Add/expand test coverage for auth behavior and error contracts. | `P2.2.8` | `tests/test_auth_service.py` (new), `tests/test_auth_api.py` (new), `tests/conftest.py` (fixtures) | `pytest tests/test_auth_service.py tests/test_auth_api.py -q`. |

### Stream A Acceptance Criteria
- [ ] Login endpoint authenticates valid credentials and returns signed token payload.
- [ ] Inactive/invalid credentials are rejected with stable auth error responses.
- [ ] `/auth/me` returns the current account context from bearer token claims.
- [ ] Stream A tests cover happy path and failure paths.

## Stream B - Account Profile Endpoints

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| B.1 | `P2.2.10 - Service - Implement authenticated profile read/update service - Stream B (Dependent)` | Add service methods for self-profile retrieval and constrained updates (Phase 2 baseline: `full_name`). | `P2.2.5` | `app/services/accounts.py` (new) or `app/services/auth.py` (extension) | Service tests for valid updates, empty/invalid payloads, inactive accounts. |
| B.2 | `P2.2.11 - API - Add account profile endpoints (GET/PATCH /api/v1/accounts/me) - Stream B (Dependent)` | Implement profile endpoints using current-account dependency and schema validation. | `P2.2.10` | `app/api/routes/accounts.py` (new), `app/api/router.py` | Route tests for 200/422/401; verify only allowed fields are mutable. |
| B.3 | `P2.2.12 - Test - Add profile API tests for validation and permissions - Stream B (Dependent)` | Cover profile read/update success/failure contracts and guard behavior. | `P2.2.11` | `tests/test_accounts_api.py` (new), `tests/conftest.py` (fixtures) | `pytest tests/test_accounts_api.py -q`. |

### Stream B Acceptance Criteria
- [ ] Authenticated users can read their own profile.
- [ ] Authenticated users can update allowed profile fields with validation.
- [ ] Unauthorized requests are rejected consistently.
- [ ] Profile tests cover both happy and edge cases.

## Stream C - Protected Routing and Access Baseline

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| C.1 | `P2.2.13 - Design - Finalize baseline role guard policy for Milestone 2 routes - Stream C (Independent)` | Define role access baseline for existing + near-term Milestone 2 routes (`analytics`, `conversations`, auth/profile). | `P2.2.1` | `docs/milestone-2/m2-phase-2.md`, optional `app/core/constants.py` notes | Review confirms policy is explicit for public/authenticated/role-restricted surfaces. |
| C.2 | `P2.2.14 - API - Apply auth guards to protected route groups and register auth router - Stream C (Dependent)` | Enforce auth dependency on protected route groups and wire new auth/profile routers into API. | `P2.2.5`, `P2.2.13` | `app/api/routes/analytics.py`, `app/api/routes/conversations.py`, `app/api/routes/auth.py`, `app/api/routes/accounts.py`, `app/api/router.py` | Route smoke checks confirm protected endpoints return 401 without valid bearer token. |
| C.3 | `P2.2.15 - Test - Add authorization tests for protected route behavior - Stream C (Dependent)` | Add coverage for missing token, invalid token, and role policy behavior. | `P2.2.14` | `tests/test_authz_guards.py` (new), route test updates | `pytest tests/test_authz_guards.py -q` plus impacted route tests. |

### Stream C Acceptance Criteria
- [ ] Protected route groups enforce bearer auth.
- [ ] Public auth endpoints remain accessible without prior auth.
- [ ] Role baseline behavior is documented and covered by tests.
- [ ] Existing route behavior is preserved aside from required auth gating.

## Stream D - Phase Validation and Handoff

| Task ID | Title | Goal / Acceptance Criteria | Dependencies | Files to Modify/Create (Expected) | Testing / Validation |
|---|---|---|---|---|---|
| D.1 | `P2.2.16 - QA - Run compile and targeted pytest verification for Phase 2 auth scope - Stream D (Dependent)` | Execute compile + focused test suite for auth/profile/guard changes. | `P2.2.9`, `P2.2.12`, `P2.2.15` | No mandatory code files; QA notes in task descriptions | `python -m compileall app/` and targeted `pytest` commands for auth/profile/guard suites. |
| D.2 | `P2.2.17 - Docs - Update task/progress docs with Phase 2 execution notes and residual risks - Stream D (Dependent)` | Sync project docs after execution/review outcomes and list remaining risks for Phase 3/6 handoff. | `P2.2.16` | `docs/tasks.md`, `docs/project-progress.md`, `docs/milestone-2/m2-phase-2.md` | Documentation review for status consistency and handoff readiness. |

### Stream D Acceptance Criteria
- [x] Compile checks pass in modified Python modules.
- [x] Targeted auth/profile/authorization tests pass (or blockers are explicitly documented).
- [x] Docs are synchronized with execution and review status.

### Stream D Execution Notes (Completed `2026-03-05`)
- `P2.2.16` executed, reviewed, and moved to `DONE`:
  - `python -m compileall app tests` passed.
  - initial sandboxed targeted pytest run failed with Docker/Testcontainers npipe permission error (`CreateFile Access is denied`).
  - rerun with unrestricted execution passed:
    - `pytest tests/test_auth_service.py tests/test_auth_api.py tests/test_accounts_api.py tests/test_authz_guards.py -q`
    - result: `30 passed`.
- `P2.2.17` executed, reviewed, and moved to `DONE`:
  - synchronized `docs/tasks.md`, `docs/project-progress.md`, and `docs/milestone-2/m2-phase-2.md` with Stream D outcomes.

### Residual Risks / Handoff Notes (`2026-03-05`)
- Environment/runtime risk: testcontainers-based suites require unrestricted Docker access in this environment; sandboxed execution is expected to fail.
- Workflow note: Phase 2 execution tasks are complete; handoff risk is limited to environment constraints above.

## Suggested Files by Concern
- Routing:
  - `app/api/router.py`
  - `app/api/routes/auth.py` (new)
  - `app/api/routes/accounts.py` (new)
  - existing protected routes under `app/api/routes/`
- Schemas:
  - `app/schemas/auth.py` (new)
  - `app/schemas/accounts.py` (new)
  - `app/schemas/__init__.py`
- Services/Security:
  - `app/services/auth.py` (new)
  - `app/services/accounts.py` (new or merged)
  - `app/core/security.py` (new)
  - auth dependency module (`app/api/deps/` or `app/db/deps.py` extension)
- Configuration:
  - `app/core/config.py`
  - `.env.example` (if project maintains one)
- Tests:
  - `tests/test_auth_service.py` (new)
  - `tests/test_auth_api.py` (new)
  - `tests/test_accounts_api.py` (new)
  - `tests/test_authz_guards.py` (new)
  - `tests/conftest.py` fixture extensions

## Component Dependency Summary
- Gate 2.0 provides the auth contract, settings, schema, and dependency primitives.
- Stream A and Stream B both depend on Gate 2.0 and can run in parallel.
- Stream C depends on Gate 2.0 and can run in parallel with A/B once guard policy is finalized.
- Stream D depends on completion of A/B/C and closes Phase 2 verification and handoff.

## Parallelization Map

```text
Gate 2.0 (P2.2.1 - P2.2.5 Auth contract + primitives) -------------+
                                                                    |
  |- Stream A (login + /auth/me) ---------------------------------> |
  |- Stream B (account profile endpoints) -------------------------> |  (parallel after Gate)
  |- Stream C (route guards + access baseline) -------------------> |
                                                                    |
  |- Stream D (compile/tests/docs sync) --------------------------> |  (after A/B/C)
                                                                    v
                  Phase 2 Complete (Auth and Accounts Foundation)
```

## Definition of Done (Phase 2)
- [ ] Auth contract and route access matrix are implemented and documented.
- [ ] Login and `/auth/me` endpoints are stable and validated.
- [ ] Account profile self-service endpoints are implemented with validation.
- [ ] Protected route groups enforce authentication consistently.
- [ ] Any schema changes (if needed) are additive-only with verified rollback.
- [ ] Auth/profile/authorization tests exist and pass for modified scope.
- [ ] No lint/syntax errors in modified Python modules.

## Test Scenarios (Phase 2 Validation)

### Happy Path
- Valid email/password returns access token and account context.
- Authenticated user can call `/auth/me` and `/accounts/me`.
- Authenticated user can patch allowed profile fields and observe persisted changes.
- Protected analytics/conversations routes return success with valid auth context.

### Edge Cases
- Wrong password / unknown email returns auth failure response.
- Inactive account cannot authenticate.
- Missing/invalid/expired token returns 401 on protected routes.
- Profile patch rejects invalid payloads (empty/oversized values).
- If Phase 2 introduces migration delta, upgrade/downgrade path remains safe.

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- JWT bearer auth is the preferred simple transport for Milestone 2 Phase 2.
- Refresh-token workflow is out of scope for Phase 2 baseline.
- Self-profile update scope is minimal (`full_name`) unless Gate 2.0 decisions expand it.
- Existing Phase 1 `accounts` schema is expected to be sufficient; migration is conditional.
- Role restrictions beyond authentication for existing `analytics`/`conversations` routes are deferred to later Milestone 2 phases (Phase 3/6 route rollout).
- Phase 2 does not include first-admin onboarding/bootstrap mechanics in app runtime; initial account provisioning is handled operationally.

### Open Questions
- None currently (resolved on 2026-03-05).

## Estimated Duration (Units)
- Gate 2.0 (`P2.2.1` - `P2.2.5`): `2.25`
- Stream A (`P2.2.6` - `P2.2.9`): `1.75`
- Stream B (`P2.2.10` - `P2.2.12`): `1.25`
- Stream C (`P2.2.13` - `P2.2.15`): `1.25`
- Stream D (`P2.2.16` - `P2.2.17`): `0.75`
- Sequential total: `7.25`
- Parallelized total after Gate (A/B/C concurrent, then D): `~4.25 - 5.0` plus Gate

## Done Condition for Phase 2 Planning
Phase 2 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-2/m2-phase-2.md`).
- Gate/stream tasks are atomic and executable with explicit dependencies.
- `docs/tasks.md` checklist includes Phase 2 task entries aligned with this plan.
- Kanban creation remains deferred unless explicitly requested.
