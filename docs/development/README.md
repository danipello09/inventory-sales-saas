# Phase 2 development setup

This repository currently contains a minimal Django/DRF backend and React/TypeScript/Vite frontend. No commercial functionality has been implemented.

For the integrated PostgreSQL and local email environment, follow
[Docker Compose development](docker-compose.md). The commands below remain available
for standalone development without Docker.

## Backend

Use Python 3.12. On Windows, create the environment with `py -3.12 -m venv .venv`
and activate it with `.\.venv\Scripts\Activate.ps1`. An existing environment keeps
the Python version with which it was created; installing Python 3.12 does not upgrade it.

```bash
cd backend
python -m venv .venv
# activate virtual environment
python -m pip install -r requirements.txt
python manage.py check
python -m pytest
python -m ruff check .
python manage.py runserver
```

Smoke endpoint: `http://127.0.0.1:8000/health/`.

## Frontend

Use Node.js 22 LTS (22.13 or newer) or Node.js 24 LTS. The declared engine range
also accepts newer releases, but LTS is the development baseline.

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build
npm audit
npm run dev
```

Frontend: `http://127.0.0.1:5173`. The development server binds to loopback by default.
Only expose it to a trusted network deliberately with `npm run dev -- --host 0.0.0.0`.

Commit `frontend/package-lock.json` with dependency changes. `npm ci` installs its
resolved dependency tree and fails if it disagrees with `package.json`.
See [the Issue #4 validation report](issue-4-validation.md) for audit findings,
remaining moderate development alerts, and the checks actually executed.

## Known gaps

- Docker Compose local services are provided by Issue #5. Further CI work belongs to Issue #6.
- Django uses SQLite only for standalone smoke checks when DATABASE_HOST is unset; integrated development will use PostgreSQL.
- Settings are intended for development smoke checks, not production deployment.
- No login, catalog, stock or sales endpoints exist.

Follow issue -> branch -> PR -> verified checks -> review -> merge. Do not claim checks passed unless executed.
