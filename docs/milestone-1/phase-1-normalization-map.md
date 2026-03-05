# Phase 1 Normalization and Enum Strategy

## Scope
This document defines canonical values and normalization rules for fields that are currently free-form or mixed-type in source data.

## Canonical Enums

### direction
- Canonical values:
  - `inbound`
  - `outbound`
- Accepted raw variants:
  - `inbound`, `incoming`, `in`, `customer` -> `inbound`
  - `outbound`, `outgoing`, `out`, `agent` -> `outbound`
- Invalid values:
  - Rejected at model validation time to avoid silent metric corruption.

### channel
- Canonical values:
  - `whatsapp`
  - `web`
  - `unknown` (fallback for unrecognized channel values)
- Accepted raw variants:
  - `wa`, `whatsapp` -> `whatsapp`
  - `web`, `website`, `webchat`, `web_chat` -> `web`
- Invalid values:
  - Normalized to `unknown` in the model layer for compatibility.

### message_type
- Canonical values:
  - `text`, `image`, `file`, `audio`, `video`, `location`, `sticker`, `unknown`
- Accepted raw variants:
  - `message` -> `text`
  - `photo` -> `image`
  - `document` -> `file`
  - `voice` -> `audio`
  - `loc` -> `location`
- Null/invalid behavior:
  - Model-layer fallback currently defaults to `text` for compatibility with source default.

### escalation booleans (legacy mixed values)
- Canonical semantic values:
  - `true`
  - `false`
  - `null` (unknown/unparseable)
- Accepted raw truthy values:
  - `true`, `yes`, `1`, `y`, `t`, boolean `true`, numeric `1`
- Accepted raw falsy values:
  - `false`, `no`, `0`, `n`, `f`, boolean `false`, numeric `0`
- Storage note:
  - Legacy chat `escalated` remains string-compatible in the initial model contract.
  - Query layer should normalize using shared helper semantics.

### conversation_grades.escalation_type
- Canonical values:
  - `Natural`
  - `Failure`
  - `None`
- Accepted raw variants:
  - Case-insensitive input is normalized to canonical capitalization.
- Null/invalid behavior:
  - Unrecognized values normalize to `null` in the model helper.

## Enforcement Strategy by Layer

### Model Layer (implemented in Phase 1)
- `app/models/enums.py` provides:
  - Enum definitions for direction/channel/message_type/escalation_type.
  - Normalization helpers for enum-like values and legacy booleans.
- `app/models/chats.py`:
  - Validates and normalizes `direction`, `channel`, and `message_type`.
  - Exposes `escalated_bool` computed normalization helper.
- `app/models/conversation_grades.py`:
  - Normalizes `escalation_type` to canonical form.

### Migration Layer (Phase 1 extension migration)
- Keep legacy chat fields flexible until baseline compatibility is verified.
- For extension tables:
  - Introduce strict enum/check constraints where safe.
  - Add score range checks (`1..10`) for grade score fields.

### Query Layer (Phase 2 analytics endpoints)
- Use shared normalization semantics for all boolean-like and enum-like filters.
- Grouping/aggregation logic must rely on canonical values only.

## Decisions and Rationale
1. `direction` is strict:
   - Bad values should fail early because direction drives core inbound/outbound metrics.
2. `channel` uses fallback:
   - Unknown channels should not block ingestion; they remain analyzable under `unknown`.
3. `message_type` defaults to `text`:
   - Aligns with existing source default and avoids null-heavy downstream handling.
4. `escalated` remains compatibility-first:
   - Source has mixed representations; hard schema coercion is deferred until migration validation.

## Follow-up for Phase 1.6 and Phase 2
- Add DB-level constraints/enums for extension tables in `P1.1.6`.
- Add endpoint-level input validation that reuses the same canonical enum maps.
- Add test cases for representative raw variants and invalid values.
