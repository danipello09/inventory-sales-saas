# API roadmap — remaining proposals

This preserves the remaining design-only endpoint outline. The routes listed as
proposals below are unimplemented. The [implemented API contract](api-contract.md)
contains only current routes; this roadmap is not an availability promise.

Inventory, movements, sales/details and minimal idempotent cancellation are now
implemented in the MVP branch; see the [live contract](api-contract.md).
Remaining planned resources include invitations/acceptance, analytics dashboards
and platform organization metadata/status.
The earlier design paths remain proposals: invitations/, invitations/accept/,
dashboard/, platform/organizations/, platform/organizations/{id}/.
Their permissions/error/transaction contracts must be finalized and tested before
implementation. Preserve same-origin sessions/CSRF, tenant scoping, decimal money,
sale snapshots, idempotent cancellation and platform-admin commercial-data denial
from the [approved ADR/TD](../adr/README.md). No invitation delivery or advanced
analytics is introduced by the MVP.
