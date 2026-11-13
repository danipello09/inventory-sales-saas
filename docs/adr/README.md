# Architecture Decision Records

Status: Approved for Phase 2 design; implementation pending.

| ID | Decision |
|---|---|
| ADR-001 | Shared PostgreSQL database with logical organization isolation |
| ADR-002 | Django session authentication using secure HttpOnly cookies and CSRF protection; same-origin deployment |
| ADR-003 | Monorepository for frontend, backend, documentation, infrastructure |
| ADR-004 | Centralized tenant-scoped authorization, relational integrity, and isolation tests; RLS may be added as defense in depth |
| ADR-005 | Variant inventory balance plus append-only stock movements |
| ADR-006 | Docker Compose local development and sanitized environment examples |

## Additional approved technical decisions

- TD-001: Unique email account; one organization membership per user in MVP.
- TD-002: Every product has at least one variant; size and color optional.
- TD-003: Decoupled invitation email service with local mail capture.
- TD-004: Single-use invitations with hashed tokens and 48-hour expiration.
- TD-005: Decimal monetary values with currency-aware validation.
- TD-006: Atomic inventory and sales transactions.
- TD-007: UUID identifiers for business entities.

## Security implications

Never trust client-provided organization IDs, prices or role claims. Scope every commercial read and write to the authenticated membership and validate cross-entity organization ownership. Platform admins may administer organization status but cannot inspect commercial data. A suspended organization retains data but cannot operate commercially. Preserve audit history and historical sale prices.

## Delivery scope

This document records decisions only. No business logic, database models, or commercial API endpoints are implemented in Phase 2.
