# MVP delivery progress and continuation

Date: 2026-11-13 America/Bogota (2026-11-14 UTC).
Branch: `feat/mvp-inventory-sales`.
Base: `681a07cb46e7b3d7c773656cb824b42da71c2eef`, main after PR #17 merged.
Implementation commit: `3600bcabdfd73a0865affe9b1eb7e92e0246c3b9`.
Documentation/evidence follow in a separate commit on this same branch.

## Recovered state and delivered scope

Original checkout was clean on its historical documentation branch. All prior
worktrees were preserved. Fetch and GitHub REST confirmed PR #17 merged before
creating a clean MVP worktree from origin/main. No identity/catalog reimplementation,
reset, force push, merge or issue closure was performed by this mission.

Implemented: balance/movement models; atomic ADMIN adjustments; ADMIN/STAFF sales;
server Decimal totals and SKU/price/currency snapshots; stock bounds and rollback;
deterministic variant/balance locks; safe first balance creation; five new tenant
composite FKs; minimal ADMIN idempotent cancellation from the existing design.
New migration count: 27. Original migration history and legacy guard unchanged.

React includes registration/login, overview, category/product/variant creation,
inventory/adjustments/history, sale entry and sale history/details/cancellation.
The API client uses same-origin cookies, JSON/CSRF and token rotation after auth;
no localStorage credentials, JWT or permissive CORS. Pagination and empty/error/
loading states are provided. The overview counts records, not financial analytics.

The [English design and API](../architecture/mvp-inventory-sales.md), updated root
README and [Spanish interview guide](../study/interview-preparation-es.md) explain
actual code, exclusions and interview exercises. Approved ADR decisions are unchanged.

## Actual checks executed

| Check | Result |
| --- | --- |
| Django system check | Passed, no issues. |
| Ruff backend | Passed; no rule relaxation. |
| makemigrations --check --dry-run | Passed, no drift. |
| Full SQLite suite | **156 passed, 30 skipped in 136.51 s**. |
| Full PostgreSQL 17.12 suite on a new owned DB | **186 passed, no skips in 191.94 s**. |
| Existing tests retained | All 164 baseline cases retained; 22 meaningful new cases (15 API + 7 PostgreSQL-only). |
| Real PostgreSQL concurrency | One of two last-unit sales succeeds; the other conflicts. Two first adjustments preserve both increments in one balance. |
| Direct PostgreSQL integrity | Cross-tenant balances/movements/items/sale references rejected by new composite FKs. |
| PostgreSQL verifier | Exit 0, 29 events. Fresh 27 migrations, idempotence, inventory tenant-DDL reverse/reapply, no old auth_user, system check/Ruff/drift and all tests. |
| Disposable legacy database | Expected migrate exit 1 before writes; actual baseline schema/history/marker preserved. |
| Compose --verify --catalog | Exit 0, 87 events. Brand-new exclusive project/volume, verified actual mount, four healthy services, real session/CSRF HTTP and scoped cleanup. |
| Real HTTP MVP | New category/product/variant, +10 adjustment, STAFF sale of 3, balance 7, total "37.50", two movements, sale detail and cross-tenant 404. |
| Frontend lint/test/build | Passed: ESLint, 3 Vitest tests in 2 files, tsc + Vite build. No dependency changes. |
| Real frontend API transport via Vite | Passed using actual frontend/src/api.ts and real HTTP/cookies: registration, logout/login, rotated CSRF, missing-CSRF 403, +10/-3=7, movement/detail and second-tenant denials. |
| Visual browser/React interaction | **BLOCKED, not passed**; see below. |

SQLite skips are the 23 existing PostgreSQL cases plus 7 new ones. SQLite success
does not certify row locks/composite FKs. Frontend fetch unit tests use controlled
responses for narrow transport checks; those are not claimed as end-to-end evidence.
The separate Node transport script mocks no API responses and does not render React.

Sanitized [PostgreSQL events](evidence/mvp-postgres-results.json) and
[Compose events](evidence/mvp-compose-results.json) match their original verifier
outputs. Private logs/manifests/env files stay outside Git. The tests ran on the
implementation source; after them only docs and a small login display-order/status
label refinement changed, with frontend lint/test/build rerun successfully.

The existing five GitHub jobs and thresholds are unchanged. Actual latest-head run
URLs/results are recorded in this branch's PR after execution; they must not be
inferred from this local report. Final diff checks, secret/artifact scan and relative
documentation-link checks are performed before publication.

## Browser blocker and exact next task

Browser inventory returned `The browser access host is unavailable`. Native Chrome
selection then stopped Computer Use with: `could not determine the current browser
URL on Windows with enough confidence to enforce policy`. No UI input or bypass
was attempted after that stop. Therefore clicks, visual layout, responsive behavior
and the complete interactive React journey are **not verified**. This mission's
full completion criteria remain pending that UI check, even though backend and
real API transport validations passed.

A new loopback-only sandbox was retained for local review; the helper printed its
private manifest and URLs. No login credentials were published. Prefer that exact
manifest's compose_argv to resume it; do not create or touch the original project.
Alternatively create another new sandbox using the root README procedure.

**Continue here without reimplementing:**

1. Check branch/status and PR latest head; preserve all changes.
2. Use an available permitted browser surface, or have the maintainer manually open
   the printed NEW frontend URL. Register synthetic organization A, sign out/in.
3. Products: category, product and variant priced 12.50. Inventory: +10 with reason.
4. New sale: add that variant, quantity 3, confirm. Inspect sale total 37.50, inventory
   7, movement history +10/-3 and sale detail. Refresh/reload to verify session.
5. Sign out; create organization B and verify empty own lists. Check mobile layout,
   field errors and the no-stock path. Optional ADMIN cancellation restores stock once.
6. Record actual observations and screenshots only after seeing them. Fix only
   observed defects, rerun affected checks and inspect the new head's five CI jobs.
7. Request technical review; keep the PR unmerged until explicit authorization.

Do not rerun the full DB suites solely because of documentation changes. Do not
use an alternative automation route to evade the Computer Use safety stop.

## Safety, limits and scope

Original PostgreSQL volume was never attached, queried or migrated. No existing
volumes were removed. Both verifier cleanups were limited to their own newly
created resources. Original four services remained healthy. The retained sandbox
has a new project and named volume; only loopback ports are published.

API history is immutable to clients, not to trusted SQL operators. No RLS,
idempotency keys for sale/adjustment POSTs, realtime synchronization or throughput
claim. Cancellation is the only idempotent business mutation. UI uses current-page
selectors and does not implement a full router. Nine moderate npm development
findings remain existing debt; no production controls were weakened.

Excluded: warehouses/transfers, suppliers/purchasing, reservations, payments, complex
tax/invoicing, promotions, returns, advanced reporting, invitations and public hosting.
Rate limiting, email verification, recovery and production settings/deployment remain
[OPEN gates](identity-public-exposure.md). This remains a local portfolio MVP.
