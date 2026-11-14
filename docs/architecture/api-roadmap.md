# API roadmap ? not implemented

This preserves the earlier design-only endpoint outline. None of these routes is
implemented by the catalog slice. The [implemented API contract](api-contract.md)
contains only current routes; this roadmap is not an availability promise.

Planned resources include invitations/acceptance, inventory balances/adjustments,
sales/details/cancellations, dashboards and platform organization metadata/status.
The earlier design paths remain proposals: invitations/, invitations/accept/,
inventory/, inventory/adjustments/, sales/, sales/{id}/, sales/{id}/cancel/,
dashboard/, platform/organizations/, platform/organizations/{id}/.
Their permissions/error/transaction contracts must be finalized and tested before
implementation. Preserve same-origin sessions/CSRF, tenant scoping, decimal money,
sale snapshots, idempotent cancellation and platform-admin commercial-data denial
from the [approved ADR/TD](../adr/README.md). No invitation delivery, inventory or
sales logic is introduced by the present module.
