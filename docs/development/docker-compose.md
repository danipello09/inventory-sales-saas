# Docker Compose development (Issue #5)

**Legacy infrastructure reference:** the default project commands below describe the
original Phase 2 environment. For the custom-user version in PR #16, use the
[new-project cutover](identity-cutover.md) and its exact manifest-specific prefix.
Do not run this checkout against the original/default project or volume.

This is a development environment, not a production deployment. It implements
ADR-001/002/003/006 and TD-003 infrastructure without business functionality.
Only the infrastructure portions are implemented; tenant isolation, authentication
flows and invitation logic remain pending. For a first setup in PowerShell or
Linux Bash, start with the [root quick start](../../README.md#quick-start-with-docker-compose).
Read [security guidance](../../SECURITY.md) before sharing logs or changing exposure.

## Requirements and preparation

Use Docker Desktop with the Linux container engine (WSL 2 on Windows), Docker
Compose v2 or newer, and Git. Python and Node are installed inside images.
The tested environment and results are recorded in [the validation report](issue-5-validation.md).

Run commands from the repository root in PowerShell. Start Docker Desktop and
confirm `docker info` works. Create `.env` only when it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env`: replace both `replace-in-local-env` values with distinct random local
values. Keep them out of Git and do not paste resolved Compose configuration into
public logs: `docker compose config` includes environment values. `.env` is
ignored; `.env.example` is a sanitized template. Compose reads `.env` for interpolation
and passes only the explicit variables each service needs. Database credentials
are never passed to Vite or included in its build context.

```powershell
docker compose config --quiet
docker compose build
docker compose up -d --wait
docker compose exec backend python manage.py migrate
docker compose ps
```

Migrations are explicit; they are not applied on every server restart. Before the
first migration, health checks can pass because `/health/` only tests HTTP liveness.
Migration warnings are expected until `migrate` completes.

## Services and boundaries

| Service | Role | Host access |
| --- | --- | --- |
| backend | Python 3.12, Django/DRF development server | http://127.0.0.1:8000/health/ |
| frontend | Node 22 LTS, React/TypeScript/Vite and HMR | http://127.0.0.1:5173/ |
| db | PostgreSQL 17, named persistent volume | No host port; use `docker compose exec db` |
| mailpit | Captures development SMTP without external delivery | http://127.0.0.1:8025/; SMTP 127.0.0.1:1025 |

Exact image versions are specified in Dockerfiles/Compose. Tags prevent implicit
major upgrades; they are not immutable digests. Review updates deliberately.
The `development` network is internal: services resolve `db`, `backend` and
`mailpit` through Docker DNS. PostgreSQL joins only this network and has no
external route. Backend, frontend and Mailpit also join `host_access`, a bridge
needed for published host ports with Docker Engine 29. Those three services can
reach the Internet; no Mailpit SMTP relay or forwarding is configured. Images
download dependencies during build using Docker's build network.

Host ports bind to 127.0.0.1. Inside the containers Django/Vite listen on 0.0.0.0
so Docker can route traffic to them. Host ports can be changed in `.env`; internal
ports and service addresses remain fixed. Backend database settings are explicitly
`db:5432`, so Compose cannot silently fall back to SQLite. PostgreSQL credentials
are for local development; the official image creates a database superuser for
initialization and this is not a production privilege model.

`depends_on: service_healthy` orders startup; `restart: true` propagates explicit
Compose dependency restarts. Health checks alone do not restart unhealthy
containers. `unless-stopped` restarts exited processes until explicitly stopped.
Application containers run as unprivileged users and use `init` for signal handling.

## Editing and dependency changes

Backend and frontend code are bind-mounted. Django autoreload and Vite HMR observe
edits. Vite polling is enabled only in Compose to support Windows/WSL file events;
standalone Vite retains normal file watching and its loopback default.

An anonymous volume at `/app/node_modules` isolates Linux dependencies from the
host's Windows installation. After changing `package.json`/`package-lock.json`,
rebuild and refresh that volume, not the PostgreSQL named volume:

```powershell
docker compose build frontend
docker compose up -d --no-deps --force-recreate --renew-anon-volumes frontend
```

For Python requirements or Dockerfile changes:

```powershell
docker compose build backend
docker compose up -d --no-deps --force-recreate backend
```

The proxy forwards `/api/` unchanged to `http://backend:8000`. It preserves the
browser Host header and same-origin requests; no wildcard CORS or CSRF exemption
is added. `/api/v1/` currently returns Django 404, since there are no business APIs.
For standalone Vite the target defaults to `http://127.0.0.1:8000`; override the
server-only `DEV_PROXY_TARGET` variable if needed. Never place secrets in `VITE_*`.

## Checks, database access and email capture

```powershell
docker compose exec backend python manage.py check
docker compose exec backend python -m pytest -q
docker compose exec backend python -m ruff check .
docker compose exec frontend npm run lint
docker compose exec frontend npm test
docker compose exec frontend npm run build
docker compose exec db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec backend python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.vendor)"
```

`npm ci` runs when building the frontend image; rebuild and refresh its anonymous
volume to change dependencies reproducibly.
The existing tests are smoke checks, not full business or tenant isolation coverage.

To capture a local test email (reserved `.test` addresses, no external recipients):

```powershell
docker compose exec backend python manage.py shell -c "from django.core.mail import send_mail; print(send_mail('Local smoke check', 'Mailpit capture works.', 'dev@inventory.test', ['recipient@inventory.test']))"
```

Open Mailpit at http://127.0.0.1:8025/. No relay/forwarding is configured and the
SMTP transport targets Mailpit only. Django outside Compose defaults to
console email; `.env` is not automatically loaded by Django. For optional standalone
SMTP capture, set the shell variables described in `.env.example`.

## Logs and lifecycle without data loss

```powershell
docker compose logs --tail=100 backend frontend db mailpit
docker compose logs -f backend
docker compose restart
docker compose restart db
docker compose up -d --wait
docker compose stop
docker compose start --wait
docker compose down
docker compose up -d --wait
```

`restart db` restarts the database process and keeps its data. `down` removes
containers/network but retains `postgres_data`. Recreating the database also
retains that volume:

```powershell
docker compose up -d --force-recreate db
docker compose up -d --wait
```

Do not use `down --volumes` or `docker volume prune` for a routine restart: these
can destroy data. Changing POSTGRES_USER/PASSWORD/DB in `.env` does not rewrite an
already initialized database. Use existing credentials or deliberately migrate
roles/database after a backup; do not delete the volume to resolve an auth error.
The Compose project name determines the volume name; keep it stable to reuse data.

## Troubleshooting

- Engine pipe missing: start Docker Desktop and select Linux containers.
- Host port occupied: change only the host port in `.env`, then run `up -d`.
- Unhealthy service: inspect `ps` and `logs`; check dependencies before restarting.
- Stale frontend packages after rebuild: refresh only frontend anonymous volumes
  with the command above. Host `node_modules` remains independent.
- `.env.example` describes Compose service names: do not export `DATABASE_HOST=db`
  into a host Python session. Standalone smoke checks still use SQLite when unset.

References: [Compose readiness](https://docs.docker.com/compose/how-tos/startup-order/),
[PostgreSQL image](https://hub.docker.com/_/postgres),
[Mailpit images](https://mailpit.axllent.org/docs/install/docker/),
[Vite server options](https://vite.dev/config/server-options).
