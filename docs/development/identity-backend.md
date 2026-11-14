# Identity and organization backend: development and API

This branch implements the first Phase 3 identity/organization slice. Its approved
design (PR #15), Phase 2 verification (PR #14) and onboarding (PR #13) are integrated
in main, along with the identity implementation from PR #16. Integration is not
production approval. This catalog branch extends that foundation; see
[catalog design](../architecture/product-catalog.md).
Start with [the mandatory new-project cutover](identity-cutover.md) and the
[tracked public-exposure gates](identity-public-exposure.md).

## Database transition: read this before running anything

**Do not point this checkout at the existing Phase 2 database or volume.** It uses
`AUTH_USER_MODEL=accounts.User`, whose primary key is UUID and whose login field
is a canonical, unique email. The old default-user schema cannot be converted by
just running migrate. The custom migrate preflight rejects a legacy auth_user
schema/history before applying migrations; it does not fake, rename or delete data.

Use a new database and separate Compose project/volume for this branch. Keep the
old checkout and original project for the existing environment. A data-preserving
upgrade of old users/framework references requires separate approval and a reviewed
conversion plan. Do not delete a volume or use `--fake` to bypass this guard.

The automated verifier below creates its own PostgreSQL container and two fresh
databases: one migrated from the actual old revision and one using the new models.
It verifies legacy rejection without schema/history/marker changes, fresh/idempotent
migrations, SQL/UUID types, all tests and a real HTTP session/CSRF lifecycle.
It never attaches the existing development volume.

### Automated isolated verification

From this checkout's root, install the unchanged backend requirements in a Python
3.12 virtual environment. **Windows PowerShell:**

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe scripts/verify_identity_database.py
```

**Linux Bash:**

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python scripts/verify_identity_database.py
```

Docker Linux, Git and network access to GitHub/registries are required. The verifier
uses random loopback ports and temporary credentials, runs pytest against PostgreSQL
17.12, and starts a temporary local Django HTTP process with DEBUG=true so local
cookies work without TLS. It cleans up only its server/container/anonymous volume,
and retains redacted logs/results in the printed temporary directory. A legacy
migrate exit code 1 is the expected negative check; other failures abort the run.

For independent SQLite tests, unset DATABASE_HOST and set EXPECT_DATABASE_VENDOR
to sqlite in your shell, then run `python -m pytest -q` from backend using its venv.
SQLite passing is supplementary; PostgreSQL migrations/tests are required.

### Compose startup and persistent sessions

Use [the safe cutover procedure](identity-cutover.md). The startup helper creates a
new, verified project and named volume with fresh credentials and ports; its manifest
records the exact explicit Compose prefix for lifecycle commands. Never substitute
the old/default project, old env file or an existing volume. The --verify variant
actually checks HTTP/session persistence after restarting only the new backend,
STAFF denial and two-organization isolation, then cleans up only its new resources.
The frontend starter is unchanged; there is no commercial authentication UI.

## Implemented HTTP contract

Base: `/api/v1/`. All writes require JSON and CSRF, including anonymous login and
registration. Unknown fields are rejected. Identity/organization responses use
Cache-Control: no-store. IDs are UUIDs. There is no organization-ID selector/list.

| Method/path | Result |
| --- | --- |
| GET auth/csrf/ | 200, `{"csrfToken":"<masked-token>"}` and HttpOnly CSRF cookie |
| POST auth/register/ | 201, user/org/ADMIN created atomically and session established |
| POST auth/login/ | 200 and session; generic 401 for wrong/unknown/inactive credentials |
| POST auth/logout/ | 204, authenticated session invalidated |
| GET auth/me/ | 200, own identity/membership; 401 without a valid active-user session |
| GET organization/ | 200, own active organization for active ADMIN or STAFF |
| PATCH organization/ | 200, own organization's name updated by active ADMIN only |

Registration payload:

```json
{"email":"owner@example.test","password":"Long-synthetic-example-729!","organization_name":"Example Store","currency":"COP"}
```

Email is trimmed/lowercased. Passwords are write-only, use Django hashing/validators
and require at least 12 characters (maximum request length 128). Currency defaults
to COP and accepts COP/USD/EUR; it is read-only after creation in this slice.
Login accepts email/password; logout accepts `{}`; update accepts `{"name":"New name"}`.
No public API creates staff, invites users, changes roles/status or accesses another
organization. Framework superusers cannot use tenant organization endpoints.

Successful register/login/me responses:

```json
{"id":"<user-uuid>","email":"owner@example.test","membership":{"role":"ADMIN","is_active":true,"organization":{"id":"<org-uuid>","name":"Example Store","currency":"COP","status":"ACTIVE"}}}
```

An active user without membership receives membership=null from me; tenant access
is forbidden. Suspended organizations and inactive memberships cannot read/update
through organization/, but the active user can inspect me and log out. Inactive
users cannot authenticate or continue using an old session. Unknown object routes
return 404. Submitted organization_id/status/currency/privilege fields are not
silently ignored: writes return validation errors and do not mutate another tenant.

## Cookie/CSRF sequence

Fetch auth/csrf/ first and retain the returned masked token. Send it as X-CSRFToken
along with same-origin cookies for unsafe requests. Django rotates session/CSRF
state at login/registration: fetch a new token afterward. Logout invalidates the
session; an old session ID cannot access me.

Both cookies are HttpOnly and SameSite=Lax. Secure is enabled when DEBUG=false;
only the explicit local DEBUG=true environment uses non-Secure cookies for HTTP.
No CORS wildcard, CSRF exemption, JWT/localStorage token or middleware removal was
introduced. Explicit csrf_protect covers anonymous login/register, which DRF's
SessionAuthentication alone does not protect. Origin checks remain active.

API errors use `{"error":{"code":"...","message":"...","details":{}}}`.
Validation errors (400) include field details; missing session is 401 with a Session
challenge; authenticated authorization/CSRF denials are 403; duplicate registration
or registering while logged in is 409; non-JSON writes are 415. Unregistered routes
still use Django's normal 404 response. Unexpected database failures are not turned
into successful or fabricated responses.

## Integrity, tests and limits

Database constraints enforce email uniqueness/canonical storage, one membership per
user, enum values and nonblank names. Non-null FKs and protected references retain
integrity; user and organization indexes support scoped membership lookups.
Registration is transactional. Name updates re-read/lock membership and organization
inside a transaction, checking active status and ADMIN role before mutation.

The test suite exercises real HTTP views, sessions, CSRF and database constraints
with at least two organizations. Authorization fixtures use actual ORM rows and
Django-created sessions; credential tests use the real login implementation and
password hasher. The independent verifier additionally uses an actual HTTP server
and cookie jar, not mocked responses. See [validation evidence](identity-validation.md).

This is a backend foundation, not a finished multi-tenant business product. The
catalog is implemented on its own branch. Inventory, sales, reports, invitations,
account verification/recovery, abuse/rate
limiting, production settings and legacy-data conversion are not implemented.
Registration conflicts can reveal account existence. Do not expose this development
API publicly. Existing dependency debt and lack of automated Python audit remain.
The five CI jobs are retained unchanged and must pass on the implementation PR.
