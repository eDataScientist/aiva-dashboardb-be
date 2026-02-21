# Milestone 1 - Phase 1 Plan: Foundation (Data + Migration + App Core)

## Goals
- Convert current schema documentation into a concrete SQLAlchemy 2.0 model contract.
- Establish Alembic migration flow for baseline and schema extensions.
- Scaffold FastAPI backend structure required for analytics endpoints.
- Add centralized config and database lifecycle management.

## Dependencies
- Schema references:
  - `docs/DATABASE_SCHEMA.md`
  - `docs/enhanced_schema.md`
- Running PostgreSQL instance for migration validation
- Python environment with FastAPI/SQLAlchemy/Alembic tooling

## Gate 1.0 - Foundation Setup
| Task ID | Title | Type | Dependencies | Expected Output |
|---|---|---|---|---|
| 1.0.1 | `P1.1.1 - Design - Audit source schemas and column semantics - Gate (Independent)` | Design | None | Field mapping notes, type conflict list |
| 1.0.2 | `P1.1.2 - Design - Define SQLAlchemy 2.0 model contract - Gate (Dependent)` | Design | 1.0.1 | Model definitions and naming decisions |
| 1.0.3 | `P1.1.3 - Design - Define enum and normalization strategy - Gate (Dependent)` | Design | 1.0.2 | Enum/value normalization map |
| 1.0.4 | `P1.1.4 - DB - Initialize Alembic environment and target metadata - Gate (Dependent)` | DB | 1.0.2 | Alembic initialized and linked to metadata |
| 1.0.5 | `P1.1.5 - DB - Create baseline migration for current schema - Gate (Dependent)` | DB | 1.0.4 | Baseline revision for existing schema |
| 1.0.6 | `P1.1.6 - DB - Add extension migration for analytics schema and indexes - Gate (Dependent)` | DB | 1.0.5 | Extension revision (grades/indexes) |
| 1.0.7 | `P1.1.7 - Infra - Scaffold FastAPI project structure and dependency set - Gate (Dependent)` | Infra | 1.0.4 | App skeleton and dependency setup |
| 1.0.8 | `P1.1.8 - Config - Implement settings and DB lifecycle hooks - Gate (Dependent)` | Config | 1.0.7 | Env settings + startup/shutdown DB lifecycle |

## Suggested Files (Initial)
- `app/main.py`
- `app/core/config.py`
- `app/db/base.py`
- `app/db/database.py`
- `app/models/` (chat, notifications, conversation grades models)
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/*.py`

## Acceptance Criteria
- [ ] SQLAlchemy models use `DeclarativeBase`, `Mapped`, `mapped_column`.
- [ ] Model contract captures key schema irregularities (quoted table names, mixed boolean-like values).
- [ ] Alembic metadata wiring is correct and revision generation works.
- [ ] Baseline + extension migrations run on clean DB.
- [ ] `alembic downgrade -1` works from latest revision.
- [ ] FastAPI app starts and `/health` endpoint responds.
- [ ] Config fails fast when required env vars are missing.

## Risks and Mitigation
- Risk: Existing data has inconsistent value formats.
  Mitigation: Document normalization map in this phase before endpoint logic.

- Risk: Quoted table names cause ORM/migration issues.
  Mitigation: Explicit `__tablename__` usage and migration validation against target DB.

- Risk: Migration drift between local and deployed DB.
  Mitigation: Keep baseline revision explicit and add verification in Phase 3.

## Done Condition for Phase 1
Phase 1 is complete when all Gate 1.0 tasks (`P1.1.1` through `P1.1.8`) are moved out of TODO and the acceptance criteria above are satisfied.
