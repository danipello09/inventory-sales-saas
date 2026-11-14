# Implemented API v1 contract

Identity/organizations and catalog from PRs #16/#17 are integrated in main. This MVP
branch adds inventory and sales. All paths below are implemented here; future-only
routes are kept in the separate [API roadmap](api-roadmap.md), not presented as live.

Base: `/api/v1/`. Sessions, HttpOnly cookies, same-origin and CSRF are retained.
Unsafe endpoints require JSON and a valid X-CSRFToken; auth/csrf/ supplies the token.

| Method | Path | Access |
| --- | --- | --- |
| GET | auth/csrf/ | Public token bootstrap |
| POST | auth/register/ | Public, CSRF; creates owner/org/ADMIN atomically |
| POST | auth/login/ | Public, CSRF |
| POST | auth/logout/ | Authenticated, CSRF |
| GET | auth/me/ | Authenticated active user |
| GET, PATCH | organization/ | Active member; PATCH ADMIN only |
| GET, POST | categories/ | Active member; POST ADMIN only |
| GET, PATCH | categories/{id}/ | Own tenant; PATCH ADMIN only |
| GET, POST | products/ | Active member; POST ADMIN only; includes 1–50 initial variants |
| GET, PATCH | products/{id}/ | Own tenant; PATCH ADMIN only |
| GET, POST | products/{id}/variants/ | Own parent; POST ADMIN only |
| GET, PATCH | products/{id}/variants/{variant_id}/ | Own parent and variant; PATCH ADMIN only |
| GET | inventory/ | ADMIN/STAFF, own variants and balances |
| POST | inventory/adjustments/ | ADMIN, atomic adjustment and movement |
| GET | inventory/movements/ | ADMIN/STAFF, own immutable API history |
| GET, POST | sales/ | ADMIN/STAFF, own sales; atomic creation |
| GET | sales/{id}/ | Own sale with historical item snapshots |
| POST | sales/{id}/cancel/ | ADMIN, restore stock once; idempotent |

STAFF reads its own catalog including inactive metadata; ADMIN writes. No automatic
platform/superuser access, inactive memberships or suspended-org commercial access.
Foreign category/product/variant UUIDs return 404. There are no HTTP DELETE or PUT
catalog methods; deactivate through PATCH instead. Fields organization_id, product_id,
roles and privileges cannot be mass-assigned. Parent product is selected by the URL.

See [catalog design, JSON examples and restrictions](product-catalog.md) for category
names, SKU/variant identity, decimal prices, deactivation and PostgreSQL guarantees.
See [identity contract](identity-organizations.md) for sessions, roles and user state.

Catalog lists are paginated: `page`, `page_size` (default 20, 1–100), stable created_at/UUID
order; shape count/next/previous/results. Filters are documented in the catalog design;
unknown/invalid filters are 400. No unbounded nested variant list is embedded in products.
Prices are plain decimal strings in requests/responses, never float money. Current
COP/USD/EUR prices use 2 decimal places and Decimal(12,2), bounded and nonnegative.

Errors use the existing error/code/message/details JSON envelope on registered
endpoints: 400 invalid input/JSON, 401 no valid active session, 403 role/state/CSRF,
404 wrong/foreign object or page, 405 unsupported method, 409 uniqueness/state
conflict, 415 non-JSON write. Unknown URL paths retain Django's ordinary 404 format.
Unexpected database failures are not hidden. No production security guarantee is made.

The [MVP inventory/sales contract](mvp-inventory-sales.md) defines payloads,
quantity bounds, snapshots, deterministic locking and cancellation. Prices, totals,
actor and organization fields are derived on the server. No movement, sale or item
edit/delete endpoint exists. All list endpoints are paginated.
