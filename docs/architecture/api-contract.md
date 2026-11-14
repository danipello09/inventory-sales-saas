# API v1 contract outline

The identity/organization backend slice is implemented on its dedicated feature
branch, subject to review; see [API and setup details](../development/identity-backend.md).
Registration, login, logout, me and organization GET/PATCH below are implemented
there, plus GET auth/csrf/ for token bootstrap. All other routes remain design only.

Base path: `/api/v1/`. Same-origin session cookies, CSRF on unsafe methods, HTTPS in production.

| Method | Path | Access |
|---|---|---|
| POST | auth/register/ | Public |
| POST | auth/login/ | Public |
| POST | auth/logout/ | Authenticated |
| GET | auth/me/ | Authenticated |
| GET,PATCH | organization/ | GET member; PATCH org admin |
| POST | invitations/ | Org admin |
| POST | invitations/accept/ | Valid invite holder |
| GET,POST | products/ | GET member; POST org admin |
| GET,PATCH | products/{id}/ | GET member; PATCH org admin |
| GET,POST | products/{id}/variants/ | GET member; POST org admin |
| GET | inventory/ | Member |
| POST | inventory/adjustments/ | Org admin |
| GET,POST | sales/ | Member |
| GET | sales/{id}/ | Member |
| POST | sales/{id}/cancel/ | Org admin |
| GET | dashboard/ | Org admin |
| GET | platform/organizations/ | Platform admin, metadata only |
| PATCH | platform/organizations/{id}/ | Platform admin, activation only |

## Conventions

- Do not trust organization identifiers or sale prices supplied by clients.
- Return 401 for unauthenticated, 403 for insufficient role, 404 for inaccessible tenant-owned objects, 409 for stock/state conflicts.
- Monetary JSON values are decimal strings, not floating-point numbers.
- Define a common error envelope, pagination, filters, idempotency strategy and request/response schemas before Phase 3.
- Invitation emails remain unimplemented in this first backend slice.

This outline does not implement or claim the remaining commercial routes. The
identity slice returns 409 for registration conflicts, 415 for non-JSON writes
and JSON errors on its registered endpoints; see its dedicated contract.
