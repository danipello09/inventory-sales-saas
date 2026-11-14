# Conceptual data model (Phase 2 draft)

The first backend feature branch now implements only User, Organization and
Membership with migrations/constraints. See [identity setup and API](../development/identity-backend.md).
The remaining entities and business integrity rules below are still design work;
this is not evidence that inventory or sales models exist.

## Entities

- User: UUID, unique email, password hash, active status.
- Organization: UUID, name, currency code, active/suspended state, created timestamp, first-sale currency lock.
- Membership: user, organization, role (ADMIN/STAFF), active; one membership per user in MVP.
- Invitation: organization, invited email, role, hashed token, expiry, consumed/revoked timestamps.
- Category: organization, name, active.
- Product: organization, category, name, active.
- ProductVariant: product, SKU, optional size/color, decimal price, active.
- InventoryBalance: variant, integer quantity >= 0, version or lockable row.
- StockMovement: organization, variant, signed delta, reason, actor, source reference, timestamp; append-only.
- Sale: organization, creator, currency, total, status, timestamp.
- SaleItem: sale, variant, quantity > 0, unit price snapshot, subtotal.
- SaleCancellation: unique sale, actor, reason, timestamp; one cancellation per sale.

## Integrity requirements

- Enforce SKU uniqueness per organization; since variant belongs to product, consider denormalized organization FK with composite tenant-aware constraints or a validated database uniqueness mechanism.
- Prevent cross-organization references among products, variants, stock movements, sales and sale items. Application checks alone are not sufficient for data integrity; specify composite constraints in final physical schema.
- Transactionally lock inventory balance rows in deterministic order before sale confirmation, check nonnegative balance, insert sale and movements atomically.
- Cancellation is admin-only and idempotent: record cancellation once, restore stock exactly once, preserve history and exclude cancelled sales from net reporting.
- Preserve price snapshots even after catalog changes.
- Currency cannot change after any first sale, even if subsequently cancelled.
- Stock adjustments require admin actor, reason and immutable movement record.

## Pending review

Finalize FK layout, indexes, category uniqueness, variant identity for no-size/no-color items, currency scale handling and deletion policy before Phase 3.
