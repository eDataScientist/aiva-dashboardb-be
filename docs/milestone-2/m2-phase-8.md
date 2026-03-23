# Milestone 2 - Phase 8: Deployment Readiness

## Goals
- Containerize the AIVA Dashboard Backend for production deployment alongside the existing PostgreSQL container (`postgres_app`) on the `n8n_default` Docker network.
- Provide idempotent startup (migrations run automatically) with a single `docker compose up -d`.
- Add CORS middleware for frontend integration.
- Harden environment configuration for container-to-container networking.

## Architecture

### Docker Networking
The live server runs PostgreSQL inside a Docker container named `postgres_app` on the `n8n_default` external network. Per `docs/DOCKER_DB_CONNECTIVITY_NOTE.md`, container-to-container connections must use the service name `postgres_app:5432`, **not** `localhost:5433`.

```
 n8n_default network
+-----------------+       +-------------------+
| aiva-backend    | ----> | postgres_app      |
| :8000           |       | :5432             |
+-----------------+       +-------------------+
        |
   host :8000
```

### Image
- Base: `python:3.12-slim`
- Runtime dependencies only (no test packages in image)
- `WORKDIR /app` so `_project_root()` in `app/core/config.py` resolves prompt assets correctly

### Entrypoint
1. `alembic upgrade head` (idempotent; skippable via `SKIP_MIGRATIONS=1`)
2. `exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`
   - Single worker: the grading scheduler runs in FastAPI lifespan; multiple workers would duplicate it.

## Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | -- | `postgresql+psycopg2://user:pass@postgres_app:5432/aiva` |
| `AUTH_JWT_SECRET` | Yes | -- | Min 32 characters |
| `GRADING_PROVIDER` | No | `mock` | `mock` or `openai_compatible` |
| `GRADING_MODEL` | No | `mock-grade-v1` | Production OpenRouter deployment should set `minimax/minimax-m2.5` |
| `GRADING_API_KEY` | Conditional | -- | Required when provider is `openai_compatible`; primary runtime key variable |
| `OPENROUTER_API_KEY` | Conditional | -- | Optional alias for `GRADING_API_KEY` when using OpenRouter |
| `GRADING_BASE_URL` | Conditional | -- | Set to `https://openrouter.ai/api/v1` for OpenRouter |
| `GRADING_BATCH_SCHEDULER_ENABLED` | No | `false` | Set to `true` to enable the nightly previous-day grading run |
| `GRADING_BATCH_SCHEDULER_HOUR_GST` | No | `1` | GST hour when the previous-day run launches |
| `CORS_ALLOWED_ORIGINS` | No | `""` | Comma-separated origins; empty disables CORS |
| `SKIP_MIGRATIONS` | No | `""` | Set to `1` to skip Alembic on startup |
| `APP_NAME` | No | `AIVA Dashboard Backend` | |
| `APP_VERSION` | No | `0.1.0` | |

See `.env.example` for the full list of tunable settings.

### Production OpenRouter Profile
For the nightly production grading run, set the deployment `.env` to:

```env
GRADING_PROVIDER=openai_compatible
GRADING_MODEL=minimax/minimax-m2.5
GRADING_API_KEY=<openrouter-api-key>
OPENROUTER_API_KEY=<openrouter-api-key>
GRADING_BASE_URL=https://openrouter.ai/api/v1
GRADING_BATCH_SCHEDULER_ENABLED=true
GRADING_BATCH_SCHEDULER_HOUR_GST=1
GRADING_BATCH_ALLOW_MOCK_PROVIDER_RUNS=false
```

Notes:
- `OPENROUTER_API_KEY` is now accepted as an alias for `GRADING_API_KEY`, but `GRADING_API_KEY` remains the primary runtime variable.
- The nightly scheduler targets the **previous GST day** and launches at `01:00 GST`.
- Leave the scheduler enabled on only one deployed backend instance at a time.

## Deployment Steps

### First-time setup
```bash
# 1. Verify postgres_app is running on n8n_default
docker network inspect n8n_default

# 2. Populate .env with credentials (already gitignored)
cp .env.example .env
# Edit .env with real DATABASE_URL, AUTH_JWT_SECRET, OpenRouter provider settings, and scheduler settings.

# 3. Build and start
docker compose build
docker compose up -d
```

### Routine operations
```bash
# View logs
docker compose logs -f aiva-backend

# Restart after code changes
docker compose build && docker compose up -d

# Run migrations manually (if SKIP_MIGRATIONS=1)
docker compose exec aiva-backend alembic upgrade head

# Stop
docker compose down
```

## Verification Checklist
1. `docker compose build` -- image builds without errors
2. `docker compose up -d` -- container starts, migrations run, health check passes
3. `docker compose exec aiva-backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"` -- returns 200
4. `curl http://localhost:8000/docs` -- OpenAPI docs accessible from host
5. `docker compose logs aiva-backend` -- no migration errors, uvicorn started
6. after the first `01:00 GST` cycle, verify a scheduled run row exists in `grading_runs`

## Troubleshooting

### Container cannot reach postgres_app
- Ensure both containers are on the `n8n_default` network: `docker network inspect n8n_default`
- Verify DNS resolution: `docker compose exec aiva-backend python -c "import socket; print(socket.getaddrinfo('postgres_app', 5432))"`
- Check that `DATABASE_URL` uses `postgres_app:5432`, not `localhost:5433`

### Migrations fail on startup
- Check logs: `docker compose logs aiva-backend`
- Verify database exists: `docker exec postgres_app psql -U arabia_insurance -d aiva -c "SELECT 1"`
- Set `SKIP_MIGRATIONS=1` temporarily and run migrations manually to debug

### Nightly grading does not run
- Confirm `GRADING_BATCH_SCHEDULER_ENABLED=true`
- Confirm `GRADING_PROVIDER=openai_compatible`
- Confirm `GRADING_BASE_URL=https://openrouter.ai/api/v1`
- Confirm `GRADING_API_KEY` or `OPENROUTER_API_KEY` is populated
- Confirm only one backend instance has the scheduler enabled
- Check `docker compose logs aiva-backend` for startup configuration errors and later run activity

### Password contains special characters
- The `@` in the password must be URL-encoded as `%40` in `DATABASE_URL`
- In `alembic.ini`, use `%%40` (doubled percent for INI interpolation)

## Files Created/Modified

| File | Action | Purpose |
|---|---|---|
| `.dockerignore` | Created | Exclude data files, caches, tests from image |
| `requirements.txt` | Modified | Runtime deps only (httpx moved from test to runtime) |
| `requirements-test.txt` | Created | Test deps referencing runtime requirements |
| `entrypoint.sh` | Created | Migration + uvicorn startup script |
| `Dockerfile` | Created | Single-stage python:3.12-slim image |
| `docker-compose.yml` | Created | Service definition on n8n_default network |
| `app/core/config.py` | Modified | Added `cors_allowed_origins` setting |
| `app/main.py` | Modified | Added CORSMiddleware (conditional) |
| `.env.example` | Modified | Docker-default DATABASE_URL, added CORS_ALLOWED_ORIGINS |
| `.env` | Modified | Populated with live credentials |
| `alembic.ini` | Modified | Fallback URL aligned to Docker target |
