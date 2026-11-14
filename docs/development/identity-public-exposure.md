# Tracked gates before public exposure

PR #16 is a local-development backend, not a production release. The review in
[PR #16](https://github.com/danipello09/inventory-sales-saas/pull/16#pullrequestreview-5900505530)
requires the following follow-ups. These are open tracked work items, not delivered
controls or promises of a response SLA. Owner: repository maintainer; each requires
a scoped implementation/review with evidence before its status can change.

| ID | Status | Follow-up and acceptance evidence required |
| --- | --- | --- |
| PUBLIC-001 | OPEN | Rate limiting/abuse controls for login and registration, including distributed-client behavior, identity/IP policy, generic failure handling, observability and tests. Review registration's account-existence disclosure. |
| PUBLIC-002 | OPEN | Email ownership verification with single-use, expiring protected tokens, no token logging, safe retry policy and tests. Registration currently establishes a session without verification. |
| PUBLIC-003 | OPEN | Account recovery with expiring/single-use tokens, non-enumerating responses, session revocation policy and takeover/abuse tests. No recovery endpoint currently exists. |
| PUBLIC-004 | OPEN | Reviewed production settings and deployment: DEBUG=false, HTTPS, Secure/HttpOnly/SameSite cookies, explicit hosts/origins, managed secrets, least-privilege DB user, production WSGI/ASGI server, backup/restore and operational monitoring. Development Compose/runserver/Mailpit are not that deployment. |

Keep every service published only on loopback until these gates have been addressed
and accepted for a concrete deployment. Do not expose via public ports or tunnels.
Passing CI, correct CSRF and tested tenant scoping do not close these follow-ups.
No rate limiting, verification, recovery or production infrastructure is added by
this hardening change. The separately blocked legacy-data conversion also requires
review before any existing data can move to the custom-user schema.

Review dependency vulnerabilities before exposure too: the previously observed npm
moderate development findings remain visible under the existing audit thresholds;
Python vulnerability scanning and a fully hashed transitive lock remain outstanding.
See [security guidance](../../SECURITY.md) and [safe cutover](identity-cutover.md).
