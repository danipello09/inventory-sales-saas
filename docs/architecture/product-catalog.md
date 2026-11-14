# Multi-organization catalog design and API

Design resolved before model implementation, based on main `72006a3` (identity
PR #16 integrated). This implements ADR-001/004, TD-002/005/007 without changing
approved decisions. No inventory, sales, invitations or commercial frontend is added.

## Relationships and database guarantees

Category, Product and ProductVariant have UUID primary keys, organization FKs,
is_active and timestamps. Product references a required Category; Variant references
a required Product. All references use PROTECT. The variant's organization is
deliberately denormalized to enforce organization-scoped SKU uniqueness.

UUID uniqueness alone does not enforce tenant integrity. Each Category and Product
also has a unique `(id, organization_id)` key. A PostgreSQL-specific reversible
migration adds composite FKs:

- Product `(category_id, organization_id)` -> Category `(id, organization_id)`.
- Variant `(product_id, organization_id)` -> Product `(id, organization_id)`.

These are real PostgreSQL constraints, DEFERRABLE INITIALLY DEFERRED, in addition
to the ordinary Django FKs. They reject cross-organization INSERT/UPDATE and
inconsistent parent organization changes at constraint-check/commit, even through direct ORM/SQL.
Django 5.2 cannot express these relations through an ordinary ForeignKey; UUID PKs
are retained and explicit migration DDL supplies the composite constraints.

Every persisted Product must have at least one Variant (active or inactive).
The API creates Product and 1–50 supplied variants in one atomic transaction.
PostgreSQL also has deferred constraint triggers: product INSERT/UPDATE checks the
final variant set; variant DELETE/reparent checks the old product. Removing/reparenting
a variant touches the old product row without changing its timestamp, serializing
competing removals; a concurrent stale repeatable-read writer must abort rather
than leave zero variants. This is a database invariant, not a CHECK with an unsafe
cross-table subquery. Physical product removal by trusted maintenance can remove
all rows atomically; no HTTP DELETE exists.

SQLite runs portable fields/checks/uniqueness and API validation, but does not install
the composite FKs or deferred minimum-variant triggers. It is supplementary smoke
testing only. Composite FKs enforce relational consistency, not SQL row visibility
or RLS: API scoping still supplies authorization. Constraint triggers protect normal
INSERT/UPDATE/DELETE transactions; privileged DDL/disabled triggers/TRUNCATE are not
supported catalog write paths. Changes to related columns must explicitly preserve
the custom DDL, since Django model-state drift checks alone cannot verify it.
PostgreSQL tests must prove those extra constraints, commit-time
rollback and concurrency. Do not deploy the catalog on SQLite.

## Names, SKU, variant identity and money

- Category names: trimmed, nonblank, at most 120 characters, display case retained.
  A unique `(organization, lower(name))` index reserves the name even when inactive.
  Other organizations may use the same name. Product names: trimmed/nonblank,
  at most 160; duplicate product names are allowed.
- SKU: trimmed uppercase ASCII, 1–64 characters; first character alphanumeric,
  remaining characters alphanumeric, dot, underscore or hyphen. Database check
  enforces canonical syntax; `(organization, sku)` is unique, including inactive
  variants. A deactivated SKU cannot be silently reused for a different identity.
- Size/color: optional strings, canonical trimmed lowercase, at most 40 chars;
  missing/blank become `""`, never NULL. Unique `(product, size, color)` means a
  plain product has exactly one no-size/no-color identity. Case/space variants
  collide. SKU can change via ADMIN PATCH; product/organization cannot.
- Price: Decimal(12,2), from 0 to 9999999999.99. HTTP accepts only plain decimal
  strings (no floats, signs, exponents, NaN or Infinity, maximum two fractional
  digits); responses always have two decimals. Current organization currencies
  COP/USD/EUR all use this two-decimal policy. DB CHECK bounds also reject numeric
  NaN. PostgreSQL numeric stores fixed scale and may round direct SQL inputs with
  excess scale; API validation rejects those inputs rather than silently round.

## Deactivation and authorization

Only active ADMIN members of active organizations write; STAFF can read their own
catalog, including inactive metadata. Inactive/no membership, suspended organization
and platform superuser access are denied with 403; no session is 401. Existing
session/CSRF implementation is reused, including JSON-only unsafe requests.
Tenant IDs and privileges are never accepted in write payloads.

No physical deletion API: PATCH is_active=false preserves UUID/history-ready
references. Category deactivation does not rewrite descendants' intrinsic flags.
Effective availability is category.active AND product.active AND variant.active
(product availability uses category/product). Reads expose is_available. Creation
requires an active category; adding variants requires an active product/category.
Metadata edits and deactivation remain possible on inactive descendants, but
reactivation/category reassignment requires an active target category/product.
No availability check is implemented as an inventory/sales operation yet; those
future services must enforce it when executing commercial transactions.

Write services lock/recheck the existing membership and organization via the
identity authorization service, then resolve every object within that organization.
This intentionally serializes writes per organization in the MVP, including category
deactivation races. PostgreSQL uniqueness still protects direct concurrent writes
that bypass service locks. Foreign UUIDs (also a variant under the wrong parent)
return 404; unknown fields/malformed input return 400, uniqueness/state conflicts
409. Unexpected database errors propagate; they are not reported as success.

## Implemented route contract

All paths are under `/api/v1/`. POST/PATCH are ADMIN + session + CSRF; GET is
ADMIN/STAFF + valid membership. DELETE/PUT are not implemented (405).

| Route | Methods |
| --- | --- |
| categories/ | GET, POST |
| categories/{id}/ | GET, PATCH |
| products/ | GET, POST |
| products/{id}/ | GET, PATCH |
| products/{id}/variants/ | GET, POST |
| products/{id}/variants/{variant_id}/ | GET, PATCH |

Lists use page-number pagination: page_size default 20, allowed 1–100. Stable order
is created_at then UUID. Invalid/unknown query fields are 400, an out-of-range page
404. Filters: is_active and available (true/false); search (name for category/product,
SKU for variant, at most 80 chars); products also category_id and exact sku; variants
also exact size/color. A foreign category filter returns an empty list, not another
tenant's data. No unbounded nested variant arrays are returned by product reads:
variant_count is annotated and variants have their own paginated endpoint.

Category POST: `{"name":"Shirts"}`. Product POST:

```json
{"category_id":"<category-uuid>","name":"Everyday shirt","variants":[{"sku":"shirt-base","price":"12.50"},{"sku":"shirt-blue-m","size":"M","color":"Blue","price":"14.00"}]}
```

Product response (POST/GET/PATCH):

```json
{"id":"<product-uuid>","category_id":"<category-uuid>","name":"Everyday shirt","is_active":true,"is_available":true,"variant_count":2,"created_at":"<timestamp>","updated_at":"<timestamp>"}
```

Variant responses contain id, product_id, sku, size, color, price (string), is_active,
is_available and timestamps. Category responses contain id/name/is_active/timestamps.
Variant POST uses the same variant object as nested creation. Product PATCH accepts
only name/category_id/is_active; variants are changed only through their own routes.
Empty PATCH and unknown/mass-assignment fields are rejected. Lists return
`{"count":0,"next":null,"previous":null,"results":[]}`. Errors reuse identity's
`{"error":{"code":"...","message":"...","details":{}}}` envelope; CSRF 403 is preserved.

## Verification and future integration

Use only the safe sandbox on a new project/volume; retain the legacy guard and old
migration history. Tests need two organizations, STAFF, inactive/suspended/platform
cases, CSRF/method denials, direct PostgreSQL FK and uniqueness violations, minimum
variants on commit, partial-create rollback, duplicate SKU races and bounded lists.
Existing identity tests remain. PostgreSQL DDL reversal/reapply must be verified on
an owned database. Inventory may later reference variant UUIDs and prices; no stock
balance, movement, sale, money totals or invitation is implemented here.

References: [ADR/TD](../adr/README.md), [data model](data-model.md),
[safe sandbox](../development/identity-cutover.md),
[PostgreSQL constraints](https://www.postgresql.org/docs/17/ddl-constraints.html),
[PostgreSQL constraint triggers](https://www.postgresql.org/docs/17/sql-createtrigger.html),
[Django composite relationship limits](https://docs.djangoproject.com/en/5.2/topics/composite-primary-key/).
