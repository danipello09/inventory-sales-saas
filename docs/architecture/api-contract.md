# API v1 contract outline (design only)

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
- Invitation emails are not sent in Phase 2.

No endpoints are implemented by this document.
