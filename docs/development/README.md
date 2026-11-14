# Phase 2 development setup

This repository currently contains a minimal Django/DRF backend and React/TypeScript/Vite frontend. The identity/organization backend is implemented in PR #16; the catalog is implemented on its own branch; inventory and sales remain unimplemented.

**Existing Phase 2 databases are incompatible with the custom user.** Start this
version using [the new-project cutover](identity-cutover.md), never the old/default
Compose project or volume. Read [public-exposure follow-ups](identity-public-exposure.md).

New contributors should start with the [root quick start](../../README.md),
[contribution workflow](../../CONTRIBUTING.md) and [security guidance](../../SECURITY.md).
This page covers optional host-tool setup; use Compose for integrated development.

For the integrated PostgreSQL and local email environment, follow
[Docker Compose development](docker-compose.md). The commands below remain available
for standalone development without Docker.

## Backend

Use Python 3.12. From the repository root, create and activate the backend environment.
**Windows PowerShell:**

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:DATABASE_HOST = ''
$env:EXPECT_DATABASE_VENDOR = 'sqlite'
```

**Linux Bash** (alternative to the Windows block):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
unset DATABASE_HOST
export EXPECT_DATABASE_VENDOR=sqlite
```

An existing environment keeps its original Python version; installing Python 3.12
does not upgrade it. Verify `python --version` after activation. If local script
policy blocks activation on Windows, invoke `.\.venv\Scripts\python.exe` directly
instead of changing machine-wide policy. Run the following in `backend` with the
environment activated; these standalone smoke checks use SQLite:

```text
python -m pip install -r requirements.txt
python manage.py check
python -m ruff check .
python -m pytest -q
python manage.py runserver
```

Smoke endpoint: `http://127.0.0.1:8000/health/`.

## Frontend

Use Node.js 22 LTS (22.13 or newer) or Node.js 24 LTS. The declared engine range
also accepts newer releases, but LTS is the development baseline.

In a second terminal, from the repository root (PowerShell or Bash):

```text
cd frontend
npm ci
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=low
npm audit --audit-level=high
npm run dev
```

Frontend: `http://127.0.0.1:5173`. The development server binds to loopback by default.
Only expose it to a trusted network deliberately with `npm run dev -- --host 0.0.0.0`.

Commit `frontend/package-lock.json` with dependency changes. `npm ci` installs its
resolved dependency tree and fails if it disagrees with `package.json`.
The [CI audit policy](ci.md#dependency-vulnerability-policy) defines the current
thresholds. Plain `npm audit` also reports moderate development findings and may
exit nonzero even when the explicit CI threshold passes. Historical findings and
executions are recorded in the Issue #4 and Issue #6 validation reports below.

## Continuous integration

[GitHub Actions quality checks](ci.md) documents the five independent CI jobs,
local reproduction, PostgreSQL isolation, logs and dependency audit thresholds.
See [Issue #6 validation](issue-6-validation.md) for actual local and remote results.

## Known gaps

- Docker Compose local services are provided by Issue #5; Issue #6 validates their
  configuration in CI without building or booting the complete development stack.
- Django uses SQLite for standalone smoke checks when DATABASE_HOST is unset;
  Compose and the integration CI job already use PostgreSQL.
- Settings are intended for development smoke checks, not production deployment.
- Identity/organization endpoints exist in PR #16; catalog endpoints are added on the catalog branch; stock and sales remain unimplemented.

Follow issue -> branch -> PR -> verified checks -> review -> merge. Do not claim checks passed unless executed.

## Documentation and evidence

- [Docker operations](docker-compose.md) and [CI commands/logs](ci.md) are current guides.
- [ADR/TD decisions](../adr/README.md), [data model](../architecture/data-model.md) and
  [API outline](../architecture/api-contract.md) distinguish approved design from implementation.
- [Spanish study notes](../study/development-workflow-es.md) explain the tools for interviews.
- Validation reports are dated evidence: [Issue #4](issue-4-validation.md),
  [Issue #5](issue-5-validation.md), [Issue #6](issue-6-validation.md) and
  [Issue #7](issue-7-validation.md). Their original branch/PR states and test counts
  describe the time of validation, not the current repository state.
