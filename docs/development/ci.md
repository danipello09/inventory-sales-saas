# GitHub Actions quality checks (Issue #6)

The existing `.github/workflows/bootstrap-validation.yml` now runs **Quality checks**.
It runs for every PR targeting `main`, pushes to `main`, and manual dispatch.
The historical filename is retained to avoid a second overlapping workflow.
Draft PRs also run checks. No path filters skip checks on documentation changes.

## Jobs and commands

All five jobs run independently on GitHub-hosted Ubuntu runners. A frontend failure
does not prevent the backend or database checks from running.

| Job ID / displayed check | Commands | Timeout |
| --- | --- | --- |
| `backend-quality` / Django checks | Python 3.12; `python -m pip install -r requirements.txt`; `python manage.py check`; `python -m ruff check .`; `python -m pytest -q` | 10 min |
| `frontend-quality` / React checks | Node 22; `npm ci`; `npm run lint`; `npm test`; `npm run build` | 10 min |
| `postgres-integration` / PostgreSQL integration | Python 3.12; requirements install; `python manage.py migrate --noinput`; `python manage.py check`; real connection/vendor query; `python manage.py makemigrations --check --dry-run`; `python -m pytest -q` | 10 min |
| `compose-validation` / Docker Compose validation | `docker compose --env-file .env.example config --quiet`; compare `config --services` with backend/db/frontend/mailpit | 5 min |
| `dependency-audit` / npm dependency audit | Node 22; `npm ci`; `npm audit --omit=dev --audit-level=low`; `npm audit --audit-level=high` | 10 min |

Python commands run in `backend`, npm commands in `frontend`, Compose at the root.
Pip caches use `backend/requirements.txt`; npm caches use
`frontend/package-lock.json`. Caches accelerate downloads, and do not replace
dependency installation. `npm ci` enforces the committed lockfile. Pip's direct
requirements are pinned, but transitive Python packages are not fully locked.

## Reading PR results and logs

Open the PR's Checks tab or the repository's Actions tab, select **Quality checks**,
then the failed job and its first failed step. Expand its log and reproduce that
command with the same runtime and environment. A nonzero exit fails the step/job;
later ordinary steps in that job are skipped. The full npm audit still runs after
a production audit failure, unless the run is cancelled, to retain both reports.
There is no `continue-on-error`, silent audit suppression or forced remediation.

Green means the commands actually completed successfully. Red requires correction;
cancelled, queued and skipped are not successful verification. A newer commit
cancels redundant PR runs using the PR number as concurrency key. Push and manual
runs use their ref; only PR runs cancel in-progress work.

The job display names **Django checks** and **React checks** are preserved.
This issue does not change branch protection or register new required checks.
Before merging, review all five checks on the latest PR commit. Making the new
checks mandatory through branch protection is a separate repository-owner decision.

## Reproduce standalone checks

Use Python 3.12 and Node 22, activate the backend virtual environment, then run
the commands in the table from their stated directories. For the SQLite job,
unset `DATABASE_HOST` and set `EXPECT_DATABASE_VENDOR=sqlite`. In PowerShell:

```powershell
$env:DATABASE_HOST = ''
$env:EXPECT_DATABASE_VENDOR = 'sqlite'
cd backend
python -m pip install -r requirements.txt
python manage.py check
python -m ruff check .
python -m pytest -q
cd ../frontend
npm ci
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=low
npm audit --audit-level=high
cd ..
```

Run each command individually and inspect its exit status. PowerShell does not
automatically stop after a failed native command; automation must check
`$LASTEXITCODE` and fail immediately. Actions' explicit bash shell fails on errors
and failed pipelines.

Validate Compose without printing a resolved configuration, in a disposable shell:

```powershell
$env:POSTGRES_DB = 'inventory_ci'
$env:POSTGRES_USER = 'inventory_ci'
$env:POSTGRES_PASSWORD = 'ci-only-disposable-password'
$env:DJANGO_SECRET_KEY = 'ci-only-disposable-django-key-not-for-production'
$env:DJANGO_DEBUG = 'false'
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example config --services
```

The workflow also fixes all four host-port variables to harmless CI values.
Explicit `--env-file .env.example` avoids reading a local `.env`; explicit CI
environment values override the sanitized template. `config --quiet` validates
interpolation, network/volume references and dependency definitions without
printing credentials. `--services` prints only service names.

For workflow syntax, expressions, action inputs and shell analysis, optionally run
`actionlint` from the root. The implementation was checked with actionlint 1.7.7.
Static analysis is not evidence that GitHub has executed a job.

## PostgreSQL isolation and local reproduction

Actions starts a fresh `postgres:17.12-bookworm` service container per integration
job and waits on `pg_isready` (5-second interval/timeout, 12 retries). Django runs
on the runner and connects to `127.0.0.1:5432`. The service has no persistent named
volume and is removed by Actions after the job, including failures.

`inventory_ci` and its initialization user/password exist only in this disposable
service. The initialization user can create pytest's separate `test_inventory_ci`
database. This is not a production privilege model. No external DB or production
secret is used. The migration command applies Django's existing migrations to
`inventory_ci`; pytest-django creates, migrates and destroys its test database.

The workflow calls `connection.ensure_connection()`, asserts
`connection.vendor == 'postgresql'`, then queries `current_database()` and
`version()`. Thus backend configuration alone cannot masquerade as a real connection.
The database smoke test also executes SQL and verifies the sessions migration
inside pytest's database. `EXPECT_DATABASE_VENDOR=postgresql` makes SQLite fallback
fail during tests. This test adds infrastructure evidence, not business coverage.

To reproduce in PowerShell without touching the local Compose database, start a
uniquely named ephemeral container from the repository root, in a disposable shell:

```powershell
$ciName = 'issue6-check-' + [guid]::NewGuid().ToString('N')
try {
    docker run -d --rm --name $ciName -p '127.0.0.1::5432' `
        -e POSTGRES_DB=inventory_ci -e POSTGRES_USER=inventory_ci `
        -e POSTGRES_PASSWORD=ci-only-disposable-password postgres:17.12-bookworm
    if ($LASTEXITCODE -ne 0) { throw 'Container startup failed' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        docker exec $ciName pg_isready -U inventory_ci -d inventory_ci
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Database readiness timed out' }
    $env:DATABASE_HOST = '127.0.0.1'
    $env:DATABASE_PORT = (docker port $ciName 5432).Split(':')[-1]
    $env:POSTGRES_DB = 'inventory_ci'
    $env:POSTGRES_USER = 'inventory_ci'
    $env:POSTGRES_PASSWORD = 'ci-only-disposable-password'
    $env:DJANGO_SECRET_KEY = 'ci-only-disposable-django-key-not-for-production'
    $env:DJANGO_DEBUG = 'false'
    $env:EXPECT_DATABASE_VENDOR = 'postgresql'
    Push-Location backend
    try {
        python manage.py migrate --noinput
        python manage.py check
        python manage.py shell -c "from django.db import connection; connection.ensure_connection(); assert connection.vendor == 'postgresql'; print(connection.vendor)"
        python manage.py makemigrations --check --dry-run
        python -m pytest -q
    } finally { Pop-Location }
} finally {
    docker rm --force --volumes $ciName
}
```

Inspect each exit code; the cleanup targets only the container created above and
its anonymous volume. Never substitute the local Compose project or its named
volume. The automated implementation validation used a bounded health wait and
explicit exit checks; the example above is an interactive sequence.

## Docker strategy and limitations

Each PR validates the Compose model and uses a real PostgreSQL service. It does
not build the application Dockerfiles or boot backend/frontend/Mailpit. Repeating
image builds, npm/pip installs and the complete four-service startup on every PR
would add cost and duplicate much of these early-phase checks. Issue #5 records
the complete local startup/healthcheck/SMTP/persistence validation.

Consequently, this CI does not catch every Dockerfile regression, image pull issue,
broken healthcheck, HMR, SMTP or runtime networking change. Re-run the documented
[Docker Compose development checks](docker-compose.md) when those files change.
A later focused container smoke job can be added if that risk/cost balance changes.
Configuration validation creates no containers or volumes and needs no teardown.

The current frontend test only verifies the component export. The backend checks
health and database infrastructure. Neither proves commercial behavior, tenant
isolation or production hardening. No coverage percentage is claimed. Python
vulnerability scanning and a fully hashed transitive Python lock are future work.

## Dependency vulnerability policy

- Production npm tree: any reported vulnerability (low or higher) fails CI.
- Entire npm tree, including development tools: high or critical fails CI.
- Low/moderate development findings remain visible in the full audit log, but
  do not fail that threshold. This policy also permits new moderate development
  findings, so reviewers must inspect audit changes rather than rely only on green.
- Review the audit on dependency-changing PRs and at least monthly. Track the
  minimatch debt in Issue #6 and its validation report until a compatible upgrade
  has been tested; the earlier Issue #4 report preserves the historical baseline.
- Test compatible upstream updates in a focused maintenance PR; update manifest
  and lockfile together, re-run lint/test/build/audits, and review advisory changes.
  No `npm audit fix --force`, incompatible override, downgrade to unsupported
  tooling or suppression is part of this issue.

The baseline was ten moderate development alerts in Issues #4/#5. This issue's
local Node 22/npm 10 run reports nine, rooted in minimatch
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249), with zero
production findings. Counts depend on the resolved tree, platform, npm and live
advisory data; a changed count alone does not prove remediation. Dependencies and
lockfile are unchanged. Registry/network errors also fail audit; missing audit
data is not treated as success.

## Security and CI concepts

Actions use reviewed full commit SHAs, with release comments, rather than mutable
major tags. Updating pins requires review. Checkout does not persist credentials;
the workflow has only `contents: read`. PR code runs through `pull_request`, with
no personal tokens, deployment permissions, real secrets or production access.
No PR title/body is interpolated into shell code. Django middleware, password
validators and secure-cookie defaults remain intact; DEBUG is false for integration.
Image tags are exact versions but are not immutable digests; runtimes and Ubuntu
receive updates within their configured version families.

For interviews: CI integrates changes frequently and checks them automatically;
CD delivers or deploys verified artifacts. This workflow implements CI only.
Jobs run in isolated machines and steps share one job's filesystem/environment.
Service containers provide disposable dependencies; healthchecks establish
readiness, while SQL verifies connectivity and the selected backend. A lockfile
fixes the npm dependency tree; a cache only speeds fetching it. Lint, types/build,
unit/smoke tests, migration checks and security audits detect different classes
of failure. A green pipeline proves only the checks actually run on that commit.

References: [PostgreSQL services in Actions](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers),
[GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use).
