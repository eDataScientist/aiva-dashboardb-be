# Phase 1 Schema Audit

## Scope
- Source documents:
  - `docs/DATABASE_SCHEMA.md`
  - `docs/enhanced_schema.md`
  - `docs/m1-phase-1.md`
- Goal:
  - Build a field-level baseline for SQLAlchemy 2.0 modeling.
  - Capture mismatches and normalization requirements before ORM design and migrations.

## Table Inventory
1. `"Arabia Insurance Chats"` (quoted table name with spaces)
2. `usage_notifications`
3. `conversation_grades` (extension table, documented in `enhanced_schema.md`)

## Canonical Model Mapping

### 1) Arabia Insurance Chats
| Source Column | Source Type (Observed) | Nullable | Canonical SQLAlchemy Target | Notes |
|---|---|---|---|---|
| `id` | `SERIAL` / `INTEGER` | No | `Mapped[int]` PK autoincrement | Straight mapping. |
| `customer_phone` | `VARCHAR` | Yes | `Mapped[str | None]` | Customer identity key part. |
| `customer_email_address` | `VARCHAR` | Yes | `Mapped[str | None]` | Customer identity key part. |
| `session_id` | `VARCHAR` | Yes | `Mapped[str | None]` | Customer identity key part. |
| `customer_name` | `VARCHAR` | Yes | `Mapped[str | None]` | Display metadata. |
| `message` | `TEXT` | Yes | `Mapped[str | None]` | Message body or media URL. |
| `direction` | `VARCHAR` | No | `Mapped[str]` (enum-like) | Normalize inbound/outbound values. |
| `channel` | `VARCHAR` | No | `Mapped[str]` (enum-like) | Normalize case and aliases (e.g., `web`, `whatsapp`). |
| `message_type` | `VARCHAR` default `'text'` | Yes | `Mapped[str | None]` (enum-like) | Source allows null and default text. |
| `intent` | `VARCHAR` | Yes | `Mapped[str | None]` | Free-text class labels, no strict enum in source. |
| `escalated` | `VARCHAR` or `BOOLEAN` | Yes | `Mapped[str | bool | None]` at ingestion boundary, normalized boolean for analytics | Highest risk mismatch. Queries currently use `LOWER(...)` semantics in docs. |
| `created_at` | `TIMESTAMP` default `NOW()` | No | `Mapped[datetime]` | Confirm timezone policy (`TIMESTAMP` vs `TIMESTAMPTZ`) in live DB. |

Implementation note:
- Preserve table name exactly as `"Arabia Insurance Chats"` in model `__tablename__`.
- Use explicit quoting behavior in ORM/migrations to avoid identifier drift.

### 2) usage_notifications
| Source Column | Source Type | Nullable | Canonical SQLAlchemy Target | Notes |
|---|---|---|---|---|
| `id` | `SERIAL` / `INTEGER` | No | `Mapped[int]` PK autoincrement | Straight mapping. |
| `message` | `TEXT` | No | `Mapped[str]` | Required message text. |
| `notification_type` | `VARCHAR` | No | `Mapped[str]` (enum-like in app layer) | Values include `warning`, `info`, `success`. |
| `customer_count` | `INTEGER` | Yes | `Mapped[int | None]` | Optional usage metadata. |
| `slab_number` | `INTEGER` | Yes | `Mapped[int | None]` | Optional usage metadata. |
| `notified_at` | `TIMESTAMP` default `NOW()` | No | `Mapped[datetime]` | Confirm timezone policy in live DB. |

### 3) conversation_grades
| Source Column | Source Type | Nullable (Assumed) | Canonical SQLAlchemy Target | Notes |
|---|---|---|---|---|
| `id` | `uuid` | No | `Mapped[UUID]` PK | Generate server-side UUID. |
| `phone_number` | `varchar` | No | `Mapped[str]` | Business key component. |
| `grade_date` | `date` | No | `Mapped[date]` | Business key component. |
| `created_at` | `timestamp` | No | `Mapped[datetime]` | Insert timestamp. |
| `<metric>_score` fields | `smallint` | Usually No | `Mapped[int]` with check intent `1..10` | Consider DB check constraints in extension migration. |
| `<metric>_reasoning` fields | `text` | Usually Yes | `Mapped[str | None]` | Narrative AI output. |
| Boolean outcome fields (`resolution`, `loop_detected`, `user_relevancy`, `escalation_occurred`) | `boolean` | Usually No | `Mapped[bool]` | Stable bool type in extension schema. |
| `escalation_type` | enum (`Natural` / `Failure` / `None`) | Usually No | `Mapped[Enum]` | Dedicated enum type in migration. |
| `intent_label` | `varchar` | Yes | `Mapped[str | None]` | Predominant intent. |
| `intent_reasoning` | `text` | Yes | `Mapped[str | None]` | Reasoning narrative. |

Constraint requirement:
- Unique constraint on (`phone_number`, `grade_date`) is required.

## Type and Semantics Conflicts
1. `escalated` dual representation:
   - Documented as `VARCHAR / BOOLEAN`.
   - Existing query patterns use `LOWER(escalated) IN ('true', 'yes')`.
   - Requires a canonical boolean interpretation map.

2. Quoted identifier and spaces:
   - `"Arabia Insurance Chats"` requires explicit quoting in ORM and Alembic.
   - High risk of generated SQL/migration mismatch if naming conventions are implicit.

3. Enum-like fields are free text in source:
   - `direction`, `channel`, `message_type`, `notification_type` are VARCHAR in source.
   - App-level normalization map is required before strict enum DB constraints.

4. Timezone ambiguity:
   - Source docs use `TIMESTAMP` without explicit timezone.
   - API trend correctness depends on timezone policy consistency.

5. Customer identity is composite fallback logic:
   - Current analytics identity uses `COALESCE(customer_phone, customer_email_address, session_id)`.
   - Must be preserved in repository/query layer design.

## Canonical Decisions to Carry Into P1.1.2
- Keep chat table physical name as `"Arabia Insurance Chats"`; do not rename in baseline.
- Model enum-like source columns as strings first; enforce normalization policy at app boundary.
- Add explicit helper for customer identity key:
  - `COALESCE(customer_phone, customer_email_address, session_id)`.
- Treat `conversation_grades` as strongly typed extension schema with explicit enum/check constraints.
- Defer hard conversion of legacy `escalated` until normalization strategy (`P1.1.3`) and migration sequencing are finalized.

## Open Questions
1. Should baseline preserve legacy `escalated` storage as text, then expose normalized computed semantics in queries, or migrate column type immediately?
2. Which timezone should be canonical for daily/hourly analytics grouping (UTC, server local, or business timezone)?
3. Is there any existing production data with out-of-contract values for `direction`, `channel`, `message_type` beyond listed variants?
4. Should `conversation_grades` use PostgreSQL enum type for `escalation_type` or a checked text column for easier future extension?

## Ready-for-Modeling Checklist
- [x] Field-level mapping drafted for all known phase-1 tables.
- [x] Conflict areas identified (typing, quoting, enum-like values, time handling).
- [x] Explicit carry-forward decisions documented for `P1.1.2`.
- [ ] Live DB introspection performed (outside docs scope) to confirm source type reality.
