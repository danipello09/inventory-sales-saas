# Phase 3 first slice: identity, sessions and organizations

Status: detailed implementation proposal for review, authorized by the autonomous
mission. This does not replace ADR-001–006 or TD-001–007, sign off Phase 2, or imply
the endpoints already exist on main. Baseline: `757cc5d`. The independent Phase 2
evidence is [PR #14](https://github.com/danipello09/inventory-sales-saas/pull/14);
onboarding remains [PR #13](https://github.com/danipello09/inventory-sales-saas/pull/13).
Implementation must be a separate PR independently based on the same main SHA,
referencing this design as a review dependency. This keeps each diff focused without
duplicating design commits and allows all five main-targeted CI jobs to run. Review
the design before accepting the implementation; no automatic merges or history
rewrites are permitted.

## Domain and database contract

| Entity | Fields and invariants |
| --- | --- |
| accounts.User | AbstractUser-derived custom model; UUID primary key, no username, canonical lowercase trimmed email up to 254 chars; email unique including case variants, password hashed by Django, is_active, staff/superuser flags and framework timestamps/permissions |
| organizations.Organization | UUID, trimmed nonblank name up to 160 chars, currency COP/USD/EUR (initial supported set, default COP), status ACTIVE/SUSPENDED, created_at/updated_at |
| organizations.Membership | UUID, user OneToOne FK and organization FK, role ADMIN/STAFF, is_active, created_at; PROTECT both referenced entities |

Real database constraints enforce unique email plus lowercase/nonempty storage,
one membership per user (MVP TD-001), valid role/status/currency and nonempty names.
Serializers validate format, lengths, allowed fields and whitespace; constraints
also protect writes outside HTTP. User unique and FK indexes support current
lookups; no speculative composite indexes or RLS are added in this slice.
Each organization can have many members; each user can belong to at most one.
Registration creates one active user, active organization and ADMIN membership
in a single transaction. There is no public endpoint to choose another organization,
change roles, create STAFF accounts, change status or invite members. Tests create
STAFF explicitly through ORM to exercise real authorization.

Currency is set at creation and read-only thereafter in this slice. No monetary
values or sales exist yet. Future sales work must preserve the approved rule that
currency cannot change after the first sale; that work is not implemented here.
Database statuses are controlled by trusted administration, not client fields.
Platform/superuser accounts do not gain tenant access automatically and cannot
use the organization endpoint, even if assigned a membership. Platform metadata
administration endpoints remain future work.

## Custom user model and migration transition

The bootstrap uses Django's default auth.User and has already applied 18 framework
migrations in the existing development database. Django warns that changing
AUTH_USER_MODEL after tables exist is not an automatic migration. The dependency
of admin.0001_initial changes when the swappable user changes, so simply adding
accounts.0001 to an already-migrated database can produce inconsistent history.

Define accounts.User in accounts.0001_initial before new databases migrate, set
AUTH_USER_MODEL=accounts.User and point Membership to settings.AUTH_USER_MODEL.
Do not fake migration history, rename tables, drop data or migrate the existing
development volume. Add a preflight migrate command which rejects the legacy
auth_user schema/history before any migration work with an actionable error.
Demonstrate this guard on a separate disposable PostgreSQL database migrated using
the old settings, and demonstrate new-schema migrations on another fresh database.
The existing volume remains attached only to the original Phase 2 checkout.

For local implementation testing use a new checkout/worktree, unique Compose
project/volume and different loopback ports. A copied settings example for a fresh
environment does not convert the old database. Preserving old users/data under the
new model requires a separately reviewed data-migration plan and explicit approval;
that transition is a documented blocker, not an operation in this mission.
Framework migration files are not edited. Rollback means returning to the old
checkout and original project, not reversing/deleting its schema.

## HTTP API contract

All routes below are proposed under `/api/v1/`. JSON only for writes; reject unknown
fields (including organization IDs, user IDs, roles, status and privilege flags).
Responses containing identity data use Cache-Control: no-store. IDs are UUID strings.

| Method / path | Access and result |
| --- | --- |
| GET auth/csrf/ | Public; 200 with masked csrfToken and CSRF cookie, no session authentication required |
| POST auth/register/ | Public, CSRF required; 201, atomically create user/org/ADMIN and establish session; 409 if already authenticated or email conflicts |
| POST auth/login/ | Public, CSRF required; 200 and session; generic 401 for unknown email, wrong password or inactive account |
| POST auth/logout/ | Authenticated, CSRF required; 204, invalidate session; works for suspended/inactive-membership organizations |
| GET auth/me/ | Authenticated; 200 with own identity and own membership (or null); available when organization suspended to explain state |
| GET organization/ | Active authenticated tenant member; 200 with own organization's metadata |
| PATCH organization/ | Active ADMIN in active organization; 200 after name-only update; STAFF forbidden |

Unknown object-specific paths such as organization/<other-uuid>/ are not registered
and return 404. No list-all endpoint exists. Client-supplied IDs cannot switch the
tenant. SessionAuthentication returns a Session challenge so unauthenticated API
requests are 401 rather than DRF's default session-only 403; authenticated denials
remain 403. The existing plain health endpoint is preserved.

### Registration request and response

```json
{"email":"owner@example.test","password":"A-long-random-example-729!","organization_name":"Example Store","currency":"COP"}
```

Password is write-only, at most 128 characters, with Django validation (minimum 12,
similarity/common/numeric validators). Case variants of email resolve to one account.
Validate passwords against an unsaved user containing the normalized email.
Registration does not send email and does not provide ownership verification yet.

```json
{"id":"<user-uuid>","email":"owner@example.test","membership":{"role":"ADMIN","is_active":true,"organization":{"id":"<org-uuid>","name":"Example Store","currency":"COP","status":"ACTIVE"}}}
```

`GET auth/me/` and successful login use the same shape. No password/hash is returned.
`PATCH organization/` accepts `{"name":"Renamed Store"}` and returns only the
organization object. Even ADMIN cannot submit currency/status/role/organization_id.
An empty update is invalid. Login accepts only email and password; logout accepts
no body fields. Safe methods never change identity, status or organization data.

### Errors

Use a consistent JSON envelope for these API endpoints, including CSRF failures:

```json
{"error":{"code":"validation_error","message":"Invalid request.","details":{"email":["Enter a valid email address."]}}}
```

| Status | Codes / meaning |
| --- | --- |
| 400 | validation_error, parse_error: invalid/unknown fields or malformed JSON |
| 401 | not_authenticated, authentication_failed: no valid session or invalid credentials |
| 403 | csrf_failed, permission_denied: CSRF, STAFF update, missing/inactive membership, suspended org or platform-account tenant access |
| 409 | conflict: duplicate email / already-authenticated registration |
| 404/405 | Unregistered route / disallowed HTTP method |

Database uniqueness catches concurrent registration after validation. Catch that
collision only after rolling back the atomic block and translate the email conflict;
unexpected IntegrityError must propagate rather than masquerade as success.
No password/token is logged. Registration conflict can reveal account existence;
email verification, abuse controls and a disclosure-resistant registration policy
must be reviewed before public exposure.

## Sessions, CSRF and tenant enforcement

Use Django sessions, not JWT. Session and CSRF cookies are HttpOnly and SameSite=Lax;
Secure follows the existing DEBUG=false default. Only explicit local HTTP debug
uses non-Secure cookies. The masked token comes from auth/csrf/, so JS need not read
the CSRF cookie. Send it as X-CSRFToken with same-origin credentials for every unsafe
request, including anonymous registration/login. Login rotates CSRF/session state;
fetch a fresh token afterward before the next unsafe request. Logout flushes session.

DRF SessionAuthentication only checks CSRF for authenticated requests. Explicitly
apply csrf_protect to unsafe identity views, including login/register, and retain
Django's middleware. Test with enforce_csrf_checks=True and real cookies/headers,
including missing token, mismatched token and hostile Origin. Do not add exemptions,
wildcard hosts, permissive CORS or trusted-origin wildcards.

Resolve membership from request.user only. STAFF can read its own organization;
only ADMIN can rename it. Inactive users cannot authenticate or use existing
sessions. Inactive memberships and suspended organizations cannot access tenant
operations; me/logout remain available for an active user. No client can unsuspend
an organization. Update services use transactions and recheck membership, role and
status while locking membership/organization rows to avoid stale authorization.

## Verification gates

Run real request/DB tests on SQLite and PostgreSQL 17, retaining the five CI jobs:
valid/invalid registration, case-insensitive and direct-DB uniqueness, required
fields and password policy, atomic rollback, login/logout and cookie flags,
generic inactive credentials, existing inactive sessions, unauthenticated access,
CSRF failures/success, roles, active/inactive memberships, two-org isolation,
rejected ID/privilege injection, missing object route, suspended orgs, platform
account denial, FK/enum/OneToOne constraints and successful fresh migrations.
Exercise the legacy guard using a real separately owned PostgreSQL legacy schema.
Check migration drift and never run these operations on the original dev volume.

No catalog, stock, sales, reports, email invitations or commercial frontend work is
included. No production readiness, coverage percentage or formal Phase 2 closure
is claimed. Rate limiting, account verification/recovery, production settings and
the old-schema data transition are explicit residual work.

References: [approved ADR/TD](../adr/README.md), [conceptual model](data-model.md),
[API outline](api-contract.md),
[Django custom-user migration constraints](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#changing-to-a-custom-user-model-mid-project),
[DRF SessionAuthentication and login CSRF](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication),
[Django CSRF](https://docs.djangoproject.com/en/5.2/howto/csrf/).
