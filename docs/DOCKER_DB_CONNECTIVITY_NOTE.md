# Docker DB Connectivity Note

## Issue Seen
The frontend container timed out connecting to Postgres:

- `ETIMEDOUT 172.17.0.1:5433`

## Root Cause
The Postgres container was published as:

- `HostIp: 127.0.0.1`
- `HostPort: 5433`

From another container, host loopback bindings are not reachable through `172.17.0.1`/`host.docker.internal` in this setup.

## Working Fix
Use container-to-container networking on the shared external network (`n8n_default`) and connect to the Postgres service alias directly:

- `DB_HOST=postgres_app`
- `DB_PORT=5432`

`docker-compose.yml` was updated to:

- attach frontend to `n8n_default` (external network)
- default DB host/port to `postgres_app:5432`

## Important Caveat
If `DB_HOST` / `DB_PORT` are set in shell or `.env`, they override compose defaults.
Remove old values like `127.0.0.1:5433` before restart.

## Bring-Up Commands
```bash
docker compose down
docker compose up -d --build
```

## Quick Verification
```bash
docker compose exec frontend sh -lc "nc -vz postgres_app 5432"
```

If that check succeeds, app-to-DB connectivity is correct.
