# MVP inventory and sales

Built on main `681a07c` (PR #17 merged). This adds only the local portfolio flow:
login → product/variants → adjustment → sale → updated stock. Identity, organization
authorization and catalog rules are reused, not redesigned. No production claim.

## Physical model and integrity

- `inventory.InventoryBalance`: UUID, organization, one-to-one variant, integer quantity
  in 0..2147483647. Missing balances read as zero in inventory; no row needs to be
  eagerly created when a catalog variant is added.
- `inventory.StockMovement`: UUID, organization, variant, signed nonzero integer delta,
  reason, actor, timestamp, optional Sale FK. There is no mutation endpoint for history.
- `sales.Sale`: UUID, organization, creator, timestamp, currency snapshot, Decimal(16,2)
  total, COMPLETED/CANCELLED, cancellation actor/reason/time.
- `sales.SaleItem`: UUID, organization, sale, variant, SKU and unit-price snapshots,
  positive quantity (1..10000), subtotal. Unique sale/variant. CHECK enforces price
  bounds and subtotal = quantity × unit_price. Total computed with Decimal on server.

Catalog migration 0003 adds only the variant `(id, organization_id)` unique target
key. No historical migration is edited. New inventory migration 0003 adds five
reversible PostgreSQL composite FKs: balance→variant, movement→variant,
movement→sale, item→variant, item→sale. Each includes organization_id. Ordinary
FKs use PROTECT; UUID possession never grants authorization. Tests deliberately
bypass HTTP to prove these database relationships reject inconsistent tenants.

Actor attribution uses trusted authenticated users reauthorized through the active
membership service. Composite FKs enforce entity relationships, not actor membership
history or SQL visibility. There is no RLS. Trusted maintenance SQL can change history;
append-only here describes the API. There is no public SQL write interface.

SQLite omits the PostgreSQL composite FKs and row locking. SQLite tests are additional
API/portable-constraint evidence, not certification of concurrency or tenant DDL.
Future schema edits must preserve custom DDL and run the PostgreSQL tests.

## Transactions and locks

`adjust_stock`, `create_sale`, `cancel_sale` run in transaction.atomic. The existing
membership/organization lock serializes business writes within one organization,
as catalog does. This simple MVP has a deliberate throughput limit, not a benchmark.
Variant rows are then locked with select_for_update; multiple variant UUIDs are
sorted consistently. Balances are created under the variant lock and then locked,
so concurrent first adjustments cannot both create an independent balance or lose
increments. Sales check effective category/product/variant availability and subtract
stock while recording sale/items/movements in that same transaction. Insufficient
stock raises 409; all effects roll back, including a newly created zero balance.

Prices come from locked catalog variants, never the request. Existing category/product
deactivation APIs acquire the same organization lock. Sale currency is captured from
organization; no currency-edit endpoint exists, satisfying the current currency lock.
Any future currency editor must forbid changing it after the first sale.

The prior design specifies admin-only idempotent cancellation. The minimum version
locks the sale, restores each item's units, appends compensating movements and marks
CANCELLED once. Repeated cancellation returns that sale without restoring again.
It never deletes the original sale/movements or rewrites price snapshots. If stock
restoration would exceed the balance bound, the whole cancellation rolls back.

## Implemented API

All paths use `/api/v1/`, JSON, session cookies, CSRF on writes and active membership.
No organization_id, price, total, actor or status field is accepted from callers.
No unauthenticated access (401); wrong role/suspended organization (403); foreign
UUID (404); malformed JSON/type/unknown field (400); stock/state conflicts (409).

| Path | Methods | Access |
| --- | --- | --- |
| inventory/ | GET | ADMIN/STAFF, own variant catalog with zero or current stock |
| inventory/adjustments/ | POST | ADMIN |
| inventory/movements/ | GET | ADMIN/STAFF, immutable own history |
| sales/ | GET, POST | ADMIN/STAFF |
| sales/{id}/ | GET | ADMIN/STAFF, own sale with at most 50 item snapshots |
| sales/{id}/cancel/ | POST | ADMIN, idempotent |

Lists return count/next/previous/results; page_size default 20, maximum 100, stable
ordering. Unknown pagination parameters are rejected. No unbounded list endpoint.

```json
{"variant_id":"<uuid>","delta":10,"reason":"Opening stock"}
```

Adjustments require signed integer delta between -10000 and 10000 excluding zero.
They can correct inactive stock, but sales require effective active availability.

```json
{"items":[{"variant_id":"<uuid>","quantity":3}]}
```

Sales accept 1..50 distinct variants, positive integers only. At a catalog price
"12.50", three units produce total "37.50" and item unit_price "12.50". HTTP money
is serialized as decimal strings. No client-side floating-point total is authoritative.
Cancellation body: `{"reason":"Entry error"}`. No sale/item edit or deletion API.

## React

`frontend/src/api.ts` uses fetch with credentials same-origin, an in-memory CSRF
token and JSON. It refreshes the token after login/registration (Django rotates it).
Sessions stay in HttpOnly cookies; passwords/tokens never enter localStorage.
`App.tsx` has login/registration, overview counts, category/product-with-variants
forms, inventory/adjustments/movements, sales entry, sale history/details/cancellation.
Lists have explicit pagination; selectors use the current category/inventory page.
ADMIN form visibility is convenience; backend enforces every permission.

Buttons disable during requests. Forms use native constraints and server validation;
empty/loading/error/success states are explicit. Responsive layout uses local system
fonts and no remote assets. API requests do not automatically retry sale/adjustment
POSTs. Network failure can leave the outcome uncertain: inspect stock/history before
retrying. Request idempotency keys, stale-tab synchronization and routing persistence
are deliberately excluded. Cancellation alone is idempotent.

## Verification and exclusions

See [validation/progress](../development/mvp-progress.md) and the
[interview guide](../study/interview-preparation-es.md). Reuse the safe sandbox
helper; never attach the old/default project or PostgreSQL volume.

No warehouses/transfers, purchasing, reserves, payments, taxes, invoices, promotions,
returns, financial reporting, invitations, public hosting or production controls.
[Public exposure gates](../development/identity-public-exposure.md) remain OPEN.

Lock semantics follow [Django select_for_update](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update)
and [PostgreSQL explicit locking](https://www.postgresql.org/docs/17/explicit-locking.html).
