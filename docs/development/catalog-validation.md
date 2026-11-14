# Product catalog — implementation and validation

Date: 2026-11-13 (America/Bogota). Branch: `feat/phase-3-product-catalog`.
Initial main/HEAD: `72006a3e39cefe281fc96c68d73d9d8b512afe6b`, confirmed after
git fetch. The original checkout and the new worktree were clean. GitHub confirmed
PR #16 merged; identity/organizations, migration protection and five CI jobs were
already integrated. No other task branch was edited.

## Scope and decisions

[The design](../architecture/product-catalog.md) was written before model changes,
covering the twelve requested design questions. It keeps UUID PKs, sessions/CSRF,
one membership per user and central organization authorization. New app catalog
contains Category, Product and ProductVariant, strict write/read serializers,
atomic services, paginated scoped views and six list/detail routes.

Category names are case-insensitively unique per tenant; product names can repeat.
SKU is canonical uppercase/unique per tenant, including inactive rows. Empty
size/color strings normalize variant identity with a unique product/size/color key.
Decimal(12,2) is nonnegative/bounded and encoded as a string. Creation includes
1–50 variants atomically. No deletion API; parent deactivation affects effective
availability without rewriting descendant flags. STAFF reads only; ADMIN writes.

PostgreSQL guarantees go beyond Python: two explicit deferred composite FKs
and deferred minimum-variant constraint triggers supplement the ordinary Django
FKs/checks/indexes. Direct DML, rollback, concurrent SKU and competing removals
are tested. SQLite does not install those custom PostgreSQL guarantees and is
not certified as a catalog deployment database. No RLS claim is made.

## Commands and actual results

Local Python 3.12.10 venv, unchanged requirements, PostgreSQL 17.12 in newly owned
containers/databases; Docker Engine 29.8.1 / Compose 5.5.1. No preexisting DB/volume
was used for migrations/tests. Baseline old auth.User was reconstructed from its
actual migrations in another disposable database, not taken from the original DB.

| Command/check | Actual result |
| --- | --- |
| `python manage.py check` | Exit 0, no issues/silenced checks. |
| `python -m ruff check .` from backend | Exit 0. |
| `python manage.py makemigrations --check --dry-run` | Exit 0, no drift. |
| `python -m pytest -q --tb=short` with SQLite | **141 passed, 23 skipped in 104.21 s**. Explicit skips need PostgreSQL semantics (19 catalog + 4 existing identity cases). |
| Backend venv Python + `scripts/verify_identity_database.py` | Exit 0; all PostgreSQL tests, fresh/idempotent migration, legacy guard, real HTTP identity checks and scoped cleanup. |
| Final PostgreSQL suite | **164 passed, no skips, in 140.69 s**. All 105 baseline identity/infrastructure cases retained; 59 catalog cases added. |
| Actual composite FK violations | Cross-tenant product/category and variant/product INSERT/UPDATE and inconsistent parent changes fail with the expected named FK, independent of API validation. |
| Database uniqueness/checks | Category case collision, SKU/option identity, noncanonical values and negative/NaN money rejected. |
| Minimum variants | Empty product cannot commit; last variant cannot be deleted/moved leaving zero. Competing removals cannot both commit, under READ COMMITTED and REPEATABLE READ. |
| SKU concurrency | Two ADMIN HTTP clients in one org: 201/409. Separate direct-ORM connections bypass service locks: one commit/one catalog_sku_unique failure. Other org unchanged. |
| PostgreSQL migration reversal | New catalog 0002 reversed to 0001, then reapplied successfully on owned DB; original migration files/history untouched. |
| Legacy migrate | Expected exit 1 before writes; tables/history/own marker preserved. |
| Fresh custom-user/catalog schema | 22 migrations, UUID user and no auth_user; repeated migrate has no pending work. |
| `scripts/start_identity_sandbox.py --verify --catalog` | Exit 0, fresh Compose project and verified new named volume; four healthy services, config --quiet, real HTTP catalog checks and scoped cleanup. |
| HTTP catalog | CSRF-free write 403, category/product 201, paginated variants/decimal string 200, foreign UUID/category 404, STAFF PATCH 403, duplicate SKU rollback 409, category deactivation affects availability. |

First catalog-only SQLite tests passed (37 cases), then the additional meaningful
boundary/HTTP concurrency cases were added and both full final suites above were
executed. No test was deleted or mocked to manufacture successful isolation.
The [PostgreSQL evidence](evidence/catalog-postgres-results.json) and
[Compose/HTTP evidence](evidence/catalog-compose-results.json) are sanitized. Private
env/manifest/logs remain outside Git; test resources were cleaned up by their unique
owned names. The original four services remained healthy and their DB was not queried.

## Reproduction

Use the [new-project cutover](identity-cutover.md), never the old/default Compose
project or Phase 2 volume. From the catalog checkout root, after venv requirements:

```powershell
backend/.venv/Scripts/python.exe scripts/verify_identity_database.py
py -3.12 scripts/start_identity_sandbox.py --verify --catalog
```

Linux Bash equivalents:

```bash
backend/.venv/bin/python scripts/verify_identity_database.py
python3.12 scripts/start_identity_sandbox.py --verify --catalog
```

The first command creates its own PostgreSQL, tests every backend module and
preserves the negative legacy check. The second uses the existing safe Compose
mechanism with an added catalog HTTP scenario. Do not rerun the old Phase 2
verifier against new code expecting its historical 18-migration counts.

## Review, delivery and limits

The implemented [API contract](../architecture/api-contract.md) lists only live
routes; [future routes](../architecture/api-roadmap.md) are explicitly separate.
The [Spanish study summary](../study/product-catalog-es.md) explains constraints and
interview tradeoffs. Diff, paths, secrets, unchanged old migrations/guard and
documentation links are reviewed before commit; actual latest-head CI job results
are recorded in the draft PR after execution, not inferred from YAML syntax.

Main is not merged/modified by this task; no issues are closed. The app is not
production-ready. Existing public-exposure gates and dependency debt remain; this
slice adds no inventory, sales, invitations, report, frontend or paid infrastructure.
Writes currently serialize on the organization row: this is an explicit MVP
simplicity/performance tradeoff, not a throughput benchmark. Future related schema
changes must preserve custom PostgreSQL DDL and future inventory/sales must use
variant UUIDs, tenant-aware relationships, effective availability and sale snapshots.
