# Milestone 1 - Phase 2 Plan: Analytics + Conversations API MVP

## Goals
- Deliver MVP analytics read endpoints for dashboard summary and trend visualizations.
- Deliver MVP conversation browsing endpoints (conversation list + full message history view).
- Reuse Phase 1 normalization rules for channel, direction, message type, and legacy escalation values.
- Provide stable request/response contracts before endpoint implementation begins.
- Keep the phase read-only against legacy chat data (no destructive schema changes).
- Prepare OpenAPI examples for frontend integration and smoke testing in Phase 3.

## Planning Analysis (Required Order)

### 1) Data Models
- Primary source: `app/models/chats.py` (`ChatMessage`)
  - Core metrics derive from:
    - `created_at`
    - `direction`
    - `channel`
    - `intent`
    - `escalated` (via normalization semantics)
    - customer identity fallback fields: `customer_phone`, `customer_email_address`, `session_id`
- `app/models/conversation_grades.py` is present in the schema but is **out of scope for MVP quality metric calculation** in Phase 2.
- MVP quality metrics use the quicksheet formula derived from chat data only:
  - `AI Quality Score = (Resolution Rate * 0.7) + (Lead Conversion Rate * 2.5)` (capped as documented)
- Canonical customer identity for chat analytics remains:
  - `COALESCE(customer_phone, customer_email_address, session_id)`
- Conversation browsing endpoints should use the same canonical identity expression for grouping/listing.
- Conversation list/detail endpoints derive heavily from:
  - `customer_name` (contact display name)
  - `message` (text content or media/file URL payload)
  - `message_type` (text/image/file/audio/video/location/sticker)
  - `created_at` (sorting and recency)
- Legacy `escalated` remains string-compatible in storage; analytics queries must normalize values to boolean semantics.
- `conversation_grades` keys by `phone_number`, so grade-based metrics may exclude email/session-only users unless explicitly defined otherwise.

### 2) Migration
- No new migration is planned for Phase 2.
- Phase 2 depends on Phase 1 extension migration being applied:
  - Alembic revision `8c17673a6641` (`conversation_grades` table + indexes/constraints)
- Endpoint implementations must tolerate:
  - empty `conversation_grades` table
  - missing/null grade score fields
- Note:
  - `conversation_grades` is not used by MVP quality endpoints, but remains available for future iterations.

### 3) Dependencies
- Completed from Phase 1:
  - FastAPI app scaffold (`app/main.py`)
  - API router bootstrap (`app/api/router.py`)
  - SQLAlchemy models and normalization helpers (`app/models/*`)
  - DB engine/session lifecycle (`app/db/database.py`)
- External runtime dependency:
  - reachable PostgreSQL instance via `DATABASE_URL`
- Documentation dependency:
  - `docs/tasks.md` remains canonical checklist for task IDs/dependencies
- Kanban status:
  - No TODO/IN PROGRESS tasks currently exist on the `aiva-dashboard-be` board
  - Planning is doc-driven only (no new Kanban tasks created)

### 4) Configuration
- Existing required config is sufficient for MVP endpoint work:
  - `DATABASE_URL`
- Phase 2 implementation should centralize analytics defaults in code (schema or constants):
  - default date window: last 30 days
  - default channel filter: `all`
- Phase 2 should also define conversation endpoint defaults:
  - conversations list pagination (`limit`, `offset`)
  - sensible max page size (to avoid large payloads)
  - full message-history endpoint returns all messages for the selected conversation in ascending time order (MVP, no pagination)
- Validation policy to define in `P1.2.1`:
  - `start_date <= end_date`
  - bounded date window (if introduced)
  - accepted channel values (`all`, `whatsapp`, `web`)
  - deterministic handling of null/unknown values in aggregations
  - conversation list pagination bounds
  - conversation identifier contract (stable key passed from list to messages endpoint)
- Timezone policy target is Gulf Standard Time (`Asia/Dubai`) to align with the metrics quicksheet (peak hours reference in GST). Server/database runtime timezone should still be verified.

### 5) Endpoints
- Planned route group: `/api/v1/analytics/*`
- Planned route group: `/api/v1/conversations/*`
- Planned endpoints (mapped to Phase 2 tasks):
  - `P1.2.2`: `GET /api/v1/analytics/summary`
  - `P1.2.3`: `GET /api/v1/analytics/message-volume-trend`
  - `P1.2.4`: `GET /api/v1/analytics/top-intents`
  - `P1.2.5`: `GET /api/v1/analytics/peak-hours`
  - `P1.2.6`: `GET /api/v1/analytics/quality-trend`
  - `P1.2.7`: `GET /api/v1/analytics/lead-conversion-trend`
  - `P1.2.9`: `GET /api/v1/conversations` (contact name + most recent message, sorted by recency)
  - `P1.2.10`: `GET /api/v1/conversations/{conversation_key}/messages` (all messages, sorted ascending by time)
  - `P1.2.8`: OpenAPI examples for all Phase 2 endpoint contracts

## Dependencies
- Phase dependency: `Phase 1 -> Phase 2`
- Task prerequisites already satisfied:
  - `P1.1.8` complete for `P1.2.1`
  - `P1.1.6` complete for `P1.2.6`

## Gate 2.0 - Shared Analytics + Conversation Contracts

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| 2.0.1 | `P1.2.1 - API - Define analytics and conversations request/response schemas - Gate (Dependent)` | API | `P1.1.8` | Shared analytics filters + conversation contract schemas + endpoint response models + validation rules |

### Gate 2.0 Scope (P1.2.1)
- Define shared request schema(s) for analytics filters:
  - `start_date`
  - `end_date`
  - `channel`
  - optional `limit`/`top_n` where relevant (or endpoint-specific schema extensions)
- Define conversation request schema(s):
  - conversation list pagination (`limit`, `offset`)
  - optional conversation list filters (channel/date) if reused
  - conversation key/path parameter contract for fetching messages
- Define shared response primitives:
  - date-series point
  - hourly bucket point
  - KPI value payloads
  - pagination-free list item payloads for charts
- Define conversation response primitives:
  - conversation summary/list item
  - conversation message item (`message_type` + raw payload)
  - paginated list wrapper (for conversations list)
- Define endpoint-specific response contracts for all Phase 2 endpoints before implementation.
- Register analytics and conversations route module skeletons (if needed) and ensure schema imports do not create circular dependencies.

### Suggested Files for Gate 2.0
- `app/api/router.py` (include analytics router)
- `app/api/routes/analytics.py` (router skeleton + endpoint stubs or placeholders)
- `app/api/routes/conversations.py` (router skeleton + endpoint stubs or placeholders)
- `app/schemas/__init__.py` (new package)
- `app/schemas/analytics.py` (shared request/response contracts)
- `app/schemas/conversations.py` (conversation list/detail contracts)

### Gate 2.0 Acceptance Criteria
- [ ] Shared filter schema validates date range ordering and channel enum values.
- [ ] Conversation list/detail schemas define sorting behavior and identifier contracts unambiguously.
- [ ] All Phase 2 endpoint response models are defined and named consistently.
- [ ] Contracts cover nullable/empty-data scenarios without ambiguous types.
- [ ] Schema docstrings/field descriptions are sufficient for generated OpenAPI readability.
- [ ] Route module location and naming are finalized for downstream stream tasks (`analytics` + `conversations`).

### Initial API Contract Outline (for P1.2.1)

#### Shared Filter Contract
- `start_date: date | None`
- `end_date: date | None`
- `channel: Literal["all", "whatsapp", "web"]` (default `all`)

#### Summary Response (P1.2.2)
- Totals:
  - `total_messages`
  - `total_customers`
  - `inbound_messages`
  - `outbound_messages`
- Quality/conversion KPIs:
  - `escalated_customers`
  - `escalation_rate_pct`
  - `resolution_rate_pct`
  - `avg_engagement`
  - `total_leads`
  - `lead_conversion_rate_pct`
  - `ai_quality_score` (capped 0-100, per quicksheet formula)

#### Trend/List Response Primitives
- `DateValuePoint`: `date`, `value`
- `DateCountPoint`: `date`, `count`
- `HourCountPoint`: `hour`, `count`
- `IntentCountPoint`: `intent`, `count`, `share_pct`

#### Conversations List Request/Response (P1.2.9)
- `ConversationListQuery`
  - `limit: int`
  - `offset: int`
  - optional `channel`, `start_date`, `end_date` (if aligned with analytics filters)
- `ConversationSummaryItem`
  - `conversation_key` (stable key derived from canonical identity contract)
  - `contact_name` (best available display name; fallback behavior documented)
  - `latest_message`
  - `latest_message_type`
  - `latest_message_at`
  - `message_count` (optional but recommended)
  - `channel` (latest or dominant channel; defined in schema description)
- `ConversationListResponse`
  - `items: list[ConversationSummaryItem]`
  - `total`
  - `limit`
  - `offset`

#### Conversation Messages Response (P1.2.10)
- `ConversationMessageItem`
  - `id`
  - `created_at`
  - `direction`
  - `message`
  - `message_type`
  - `channel`
  - `intent`
  - `escalated`
- `ConversationMessagesResponse`
  - `conversation_key`
  - `contact_name`
  - `messages: list[ConversationMessageItem]` (sorted ascending by `created_at`)

## Stream A - Core Volume KPIs

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| A.1 | `P1.2.2 - API - Implement summary endpoint aggregates - Stream A (Dependent)` | API | `P1.2.1` | Summary KPI endpoint returning counts and derived rates |
| A.2 | `P1.2.3 - API - Implement message volume trend endpoint - Stream A (Dependent)` | API | `P1.2.1` | Daily message counts trend endpoint |

### Stream A Implementation Notes
- Read-only aggregate queries against `"Arabia Insurance Chats"`.
- Reuse canonical customer identity expression in SQL.
- Normalize escalation semantics using the same accepted truthy/falsy map documented in Phase 1.
- Summary KPI rate percentages should use **selected-range unique customers** as the denominator.
- `P1.2.3` should return a stable date-ordered series and explicit empty series for no-data ranges.

### Suggested Files (Stream A)
- `app/api/routes/analytics.py`
- `app/schemas/analytics.py`
- `app/services/analytics.py` (or `app/repositories/analytics.py`; choose one and keep consistent)
- `app/db/__init__.py` or dependency helper module (only if a request-scoped session dependency is added)

### Stream A Acceptance Criteria
- [ ] Summary endpoint returns deterministic counts/rates for date + channel filters.
- [ ] Message volume trend groups by date and sorts ascending.
- [ ] Null/empty identifiers do not break distinct-customer calculations.
- [ ] Division-by-zero paths return safe values (e.g., `0.0`) rather than errors.

## Stream B - Intent and Hourly Distribution

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| B.1 | `P1.2.4 - API - Implement top intents endpoint - Stream B (Dependent)` | API | `P1.2.1` | Top-N intents endpoint with counts/share |
| B.2 | `P1.2.5 - API - Implement peak hours endpoint - Stream B (Dependent)` | API | `P1.2.1` | Hourly activity distribution endpoint |

### Stream B Implementation Notes
- `top-intents` should include a normalized `"Unknown"` bucket for null/blank/whitespace intents.
- `peak-hours` should always return all 24 hours (`0..23`) with zero-filled buckets for missing hours.
- Channel/date filters should be shared and consistent with Stream A.

### Suggested Files (Stream B)
- `app/api/routes/analytics.py`
- `app/schemas/analytics.py`
- `app/services/analytics.py` (or `app/repositories/analytics.py`)

### Stream B Acceptance Criteria
- [ ] Top intents endpoint applies consistent ranking and tie handling.
- [ ] Peak hours endpoint output hour format is documented and stable.
- [ ] Peak hours endpoint returns a zero-filled `0..23` series for every response.
- [ ] Endpoints do not regress when `intent` is null/blank in source rows.
- [ ] Optional `limit/top_n` validation (if implemented) is bounded and documented.

## Stream C - Quality and Conversion Trends + OpenAPI Examples

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| C.1 | `P1.2.6 - API - Implement quality trend endpoint - Stream C (Dependent)` | API | `P1.2.1`, `P1.1.6` | Daily quality trend endpoint using the quicksheet chat-derived formula |
| C.2 | `P1.2.7 - API - Implement lead conversion trend endpoint - Stream C (Dependent)` | API | `P1.2.1` | Daily lead conversion counts/rates trend endpoint |
| C.3 | `P1.2.8 - API - Add OpenAPI examples for Phase 2 endpoints - Stream C (Dependent)` | API | `P1.2.2`, `P1.2.4`, `P1.2.6`, `P1.2.9`, `P1.2.10` | Example payloads and query parameter examples in generated docs for analytics + conversations |

### Stream C Implementation Notes
- `quality-trend` definition must be finalized before coding:
  - MVP decision: use quicksheet AI Quality Score formula from chat-derived metrics only
  - Do not use `conversation_grades` in MVP quality endpoints
- `lead-conversion-trend` should align with documented high-value intents:
  - `New Get-A-Quote Form Submitted in UAE`
  - `New Contact Form Submitted`
- Trend percentage denominators should use **day-specific unique customers** for each date point (not whole-range unique customers).
- OpenAPI examples should include:
  - no-data result example
  - channel-filtered example
  - normal populated result example
  - conversations list example (contact name + latest message)
  - conversation messages example (chronological mixed message types)

### Suggested Files (Stream C)
- `app/api/routes/analytics.py`
- `app/schemas/analytics.py`
- `app/services/analytics.py` (or `app/repositories/analytics.py`)

### Stream C Acceptance Criteria
- [ ] Quality trend endpoint uses the quicksheet formula (chat-derived resolution + lead conversion) and documents the formula in schema descriptions and/or code comments.
- [ ] Lead conversion endpoint uses canonical intent list and returns date-ordered series.
- [ ] OpenAPI examples match actual response schemas and field names.
- [ ] Example payloads include realistic date and channel filter usage.

## Stream D - Conversation List and Message History

| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| D.1 | `P1.2.9 - API - Implement conversations list endpoint - Stream D (Dependent)` | API | `P1.2.1` | Paginated conversation list endpoint sorted by most recent message timestamp |
| D.2 | `P1.2.10 - API - Implement conversation messages endpoint - Stream D (Dependent)` | API | `P1.2.1`, `P1.2.9` | Full message-history endpoint for one conversation sorted ascending by message time |

### Stream D Implementation Notes
- Conversation grouping key must be derived from the canonical identity expression:
  - `COALESCE(customer_phone, customer_email_address, session_id)`
- Conversation list endpoint should return:
  - contact name
  - most recent message
  - most recent message timestamp
  - sorted by recency descending
- Contact name selection rule must be explicit:
  - use the best available non-empty `customer_name` for the conversation (prefer latest non-empty observed value for MVP)
- Conversation messages endpoint should return **all messages** for the selected conversation in MVP.
- Messages must be sorted by `created_at ASC` so mixed content types (text/images/files/audio/etc.) preserve chronological order.
- Preserve raw `message` payload and expose `message_type` so the frontend can render images/files/other media correctly.

### Suggested Files (Stream D)
- `app/api/routes/conversations.py`
- `app/schemas/conversations.py`
- `app/services/conversations.py` (or shared `app/services/analytics.py` if intentionally combined)

### Stream D Acceptance Criteria
- [ ] Conversations list endpoint returns items sorted by latest message timestamp descending.
- [ ] Each conversation list item includes contact name and latest message fields.
- [ ] Conversation messages endpoint returns all messages for a conversation sorted ascending by `created_at`.
- [ ] Message payload preserves `message_type` and raw message content for non-text entries (images/files/etc.).
- [ ] Conversation selection uses the same canonical identity logic as analytics distinct-customer calculations.

## Component Dependency Summary
- `app/api/routes/analytics.py`
  - Depends on `app/schemas/analytics.py`
  - Depends on analytics query/service module
- `app/api/routes/conversations.py`
  - Depends on `app/schemas/conversations.py`
  - Depends on conversation query/service module
- `app/schemas/analytics.py`
  - Depends on Pydantic/FastAPI typing only (should avoid DB/model imports)
- `app/schemas/conversations.py`
  - Depends on Pydantic/FastAPI typing only (should avoid DB/model imports)
- `app/services/analytics.py` (or `app/repositories/analytics.py`)
  - Depends on `app/db/database.py` session factory and SQLAlchemy query/text APIs
  - Depends on normalization semantics from `app/models/enums.py` (shared truthy/falsy rules)
- `app/services/conversations.py` (or `app/repositories/conversations.py`)
  - Depends on `app/db/database.py` session factory and SQLAlchemy query/text/window-function APIs
  - Depends on canonical identity grouping rules used in analytics

## Parallelization Map

```text
Gate 2.0 (P1.2.1 Shared Analytics + Conversation Schemas) -----+
                                                                |
  |- Stream A (Summary + Volume Trend) -----------------------> |
  |- Stream B (Top Intents + Peak Hours) --------------------> |  (parallel after Gate)
  |- Stream C (Quality + Lead Conversion + OpenAPI) ---------> |
  |- Stream D (Conversations List + Messages) ---------------> |
                                                                |
  Note: C.3 depends on outputs from A.1, B.1, C.1, D.1, D.2    |
                                                                v
                         Phase 2 Feature Implementation Complete
```

## Definition of Done (Phase 2)
- [ ] `P1.2.1` through `P1.2.10` implemented and moved out of TODO in the working checklist/Kanban flow.
- [ ] Analytics and conversations routes are registered under versioned API paths.
- [ ] All endpoint contracts validate filters consistently.
- [ ] Aggregations are deterministic for empty data, nulls, and mixed legacy `escalated` values.
- [ ] Conversation list/detail endpoints honor required sort order (list by recency desc, messages asc).
- [ ] OpenAPI docs render usable endpoint examples for frontend consumers across analytics and conversations.
- [ ] No lint errors in files touched by Phase 2 work.
- [ ] Modified Python modules pass compile checks (Phase 3 gate will verify formally).

## Test Scenarios (for Phase 3 Execution Prep)

### Happy Path
- Summary endpoint for default last-30-days and `channel=all`
- Summary endpoint filtered to `channel=whatsapp`
- Message volume trend over populated date range
- Top intents returns sorted top N
- Peak hours returns expected hourly distribution
- Quality trend returns series using the quicksheet chat-derived formula
- Lead conversion trend returns counts/rates for known conversion intents
- Conversations list returns contact names + latest messages sorted by recency
- Conversation messages endpoint returns full history sorted ascending by time (text/images/files/etc.)

### Edge Cases
- Date range with no rows returns empty series and zero-valued KPIs
- `start_date > end_date` validation error
- Unsupported channel value validation error
- Null/blank intent rows do not break ranking
- Mixed `escalated` raw values (`true`, `yes`, `0`, `False`) normalize correctly
- Conversations with null/blank `customer_name` fall back to documented contact name behavior
- Conversation list pagination bounds (`limit`, `offset`) validation errors
- Conversation key not found returns a documented not-found response

## Open Questions and Assumptions

### Assumptions (Planning Baseline)
- Daily/hourly grouping is performed in Gulf Standard Time (`Asia/Dubai`) to align with the metrics quicksheet.
- Channel filter accepts only `all`, `whatsapp`, `web` for MVP.
- All endpoints are read-only and do not require authentication in Milestone 1.
- Query implementation will use SQLAlchemy Core/ORM sessions via existing session factory (not `databases` package in this codebase).
- `top-intents` includes an `Unknown` category for null/blank intents.
- `peak-hours` always returns `0..23` with zero-filled buckets.
- MVP quality trend ignores `conversation_grades` entirely and uses chat-derived quicksheet formula.
- Summary KPI percentages use **selected-range unique customers** as the denominator.
- Trend-rate percentages (e.g., lead conversion trend points) use **day-specific unique customers** as the denominator.
- Conversations list is paginated; conversation messages endpoint returns full message history for MVP.
- Conversation detail endpoint path uses a schema-defined `conversation_key` produced by the list endpoint (exact encoding/format finalized in `P1.2.1`).

### Open Questions (Need Confirmation Before/During P1.2.1)
- None blocking for MVP contract planning.

### Timezone Confirmation Note (Planning Evidence)
- `chats_180226_0852.csv` shows `created_at` / `timestamp` values with explicit `+00` offsets (UTC), e.g. `2025-11-03 09:46:07.045+00`.
- Phase 2 analytics queries should therefore bucket timestamps in `Asia/Dubai` by converting from UTC before daily/hourly grouping.

## Estimated Duration (Units)
- Gate 2.0 (`P1.2.1`): `1.0`
- Stream A (`P1.2.2` + `P1.2.3`): `2.0`
- Stream B (`P1.2.4` + `P1.2.5`): `1.75`
- Stream C (`P1.2.6` + `P1.2.7` + `P1.2.8`): `2.75`
- Stream D (`P1.2.9` + `P1.2.10`): `2.25`
- Sequential total: `9.75`
- Parallelized total after Gate (A/B/C/D concurrent): `~4.0 - 4.75` plus Gate

## Done Condition for Phase 2 Planning
Phase 2 planning is ready when:
- A dedicated phase plan document exists (`docs/milestone-1/m1-phase-2.md`)
- Gate/stream tasks align with `docs/tasks.md`
- Dependencies and open questions are explicit enough to start `P1.2.1`
