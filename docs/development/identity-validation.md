# Identity/organization slice — validation evidence

Date: 2026-11-13 (America/Bogota). Base main: `757cc5d`.
Branch: `feat/phase-3-identity-organizations`.
Review dependencies: design PR #15, Phase 2 evidence PR #14, onboarding PR #13.
All remain separate; no merge or issue closure is performed by this mission.

## Executed evidence

Python 3.12.10 venv created specifically for this worktree; unchanged requirements
installed successfully. PostgreSQL 17.12 runs in a new disposable container with
two owned databases and a random loopback host port. The original checkout,
default-user volume and four development services are untouched.

| Command/check | Actual result |
| --- | --- |
| `python manage.py makemigrations accounts organizations` | Generated two initial business-foundation migrations; framework migrations unchanged. |
| `python manage.py check` | Exit 0. |
| `python -m ruff check .` from backend | Exit 0. |
| `python manage.py makemigrations --check --dry-run` | Exit 0, no changes detected. |
| `python -m pytest -q` with SQLite | Exit 0; **52 passed in 18.96 s**. |
| `backend/.venv/.../python scripts/verify_identity_database.py` | Exit 0, complete PostgreSQL/legacy/HTTP validation. |
| Real legacy schema | Baseline main migrations actually applied to identity_legacy: 18 framework migrations, auth_user present. |
| New migrate command against legacy | Expected exit 1, explicit Legacy auth.User error before changes; table set, migration history and own marker unchanged. |
| Fresh PostgreSQL schema | Exit 0; accounts.User UUID field, 20 total migrations, no auth_user table. |
| Repeated migrate on fresh schema | Exit 0, no migrations to apply. |
| PostgreSQL `pytest -q` | Exit 0; **52 passed in 20.51 s**. |
| Real HTTP with cookie jar | Health 200; anonymous registration without CSRF 403; token 200; registration 201; me/org 200; rename 200; logout 204; old access 401; login 200 and me 200. |
| Cleanup | Owned server/container/anonymous volume removed; existing development services still healthy. |

The [sanitized structured results](evidence/identity-postgres-results.json) preserve
the successful run without personal paths or secrets. Detailed redacted logs and
the baseline clone remain in the printed identity-postgres-* temporary directory.
The verifier uses real PostgreSQL, HTTP and framework behavior; no fabricated
success response or authentication-backend stub is used.

## Findings corrected during implementation

The first SQLite run found an error-envelope mismatch (DRF's default `invalid`
versus the designed `validation_error`); the handler was corrected. PostgreSQL
then exposed a test fixture whose oversized currency failed the varchar length
before its intended enum constraint; it now uses a three-character invalid value.
CSRF middleware reading multipart data can precede DRF parsing, so JSON-only writes
also have an explicit media-type gate. New tests require 415 for multipart, reject
old pre-login CSRF tokens, and verify logout does not accept injected fields.
No failing assertion was removed to manufacture a passing result.

## Coverage and residual risk

Tests exercise registration validation/rollback, case-insensitive email and DB
constraints, password hashing/policy, login/logout/session rotation, active/inactive
accounts, HttpOnly/Secure/SameSite flags, anonymous/authenticated CSRF and hostile
Origin, STAFF/ADMIN, missing/inactive membership, suspended organization, platform
account denial, protected FKs, invalid roles/status/currency and two-org isolation.
Checks scope the implemented metadata API only, not future catalog/inventory/sales.

Legacy data conversion is deliberately blocked. A migration plan and authorization
are required before carrying old users/data to the custom-user schema. Do not delete
or fake the existing database. Rate limiting, email verification/recovery and
production operational controls remain future work. Known npm moderate development
findings are not remediated by this slice; no Python audit was added.

Implementation commit `77dc8b221394757979692b3db80939bccede0151` is published in
[draft PR #16](https://github.com/danipello09/inventory-sales-saas/pull/16).
[Quality checks #15](https://github.com/danipello09/inventory-sales-saas/actions/runs/43529168981)
completed successfully; every job and step was inspected:

| Remote job | Actual result |
| --- | --- |
| Django checks | success, Python 3.12.16, 52 passed in 9.40 s, check and Ruff passed. |
| PostgreSQL integration | success, PostgreSQL 17.12 real connection, fresh migrations/no drift, 52 passed in 8.29 s. |
| React checks | success, Node 22.23.4/npm 10.9.9, npm ci/lint, 1 test and build. |
| Docker Compose validation | success, configuration and four expected services. |
| npm dependency audit | success by thresholds, 0 production and 9 moderate development findings visible. |

The follow-up documentation commit records this evidence. Its latest checks are
also recorded in the PR description so a previous run is not attributed to a new
HEAD. Frontend and workflow code are unchanged. No local frontend re-run is claimed
for this slice (the earlier Phase 2 run did execute it). Human review remains pending.
