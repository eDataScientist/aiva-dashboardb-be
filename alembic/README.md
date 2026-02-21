# Alembic Migration Setup

## URL Resolution Order
1. `ALEMBIC_DATABASE_URL`
2. `DATABASE_URL`
3. `sqlalchemy.url` in `alembic.ini`

## Common Commands
```bash
alembic -c alembic.ini current
alembic -c alembic.ini revision --autogenerate -m "message"
alembic -c alembic.ini upgrade head
alembic -c alembic.ini downgrade -1
```

## Metadata Wiring
- `alembic/env.py` imports `app.models` to register all tables.
- `target_metadata` is loaded from `app.db.get_target_metadata()`.

