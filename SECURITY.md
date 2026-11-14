# Development security guidance

This project has a development identity/organization slice and no production release or real customer service.
There is no supported-release matrix, security response SLA, dedicated incident
team or guaranteed response time. Do not deploy the development stack as a
production system or load customer data into it.

The first identity/organization backend is local-only development. The
[tracked public-exposure gates](docs/development/identity-public-exposure.md) remain
OPEN: rate limiting, email verification, account recovery and production settings.
Use only the [new-project cutover](docs/development/identity-cutover.md); never reuse
the existing Phase 2 PostgreSQL volume.

## Configuration and secrets

- `.env.example` is a committed template containing placeholders. Copy it to
  `.env` only if the local file does not already exist, then replace
  `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` with distinct random local values.
- `.env` and local environment variants are ignored by Git; sanitized examples
  are intentionally allowed. `.gitignore` does not untrack files already committed.
  Inspect staged changes before every commit and verify `git check-ignore .env`.
- Compose reads `.env` for interpolation and passes explicitly declared values
  to services. Standalone Django does not load `.env` automatically: use shell
  environment variables. Inside Compose the database host is `db`; on the host,
  that service name does not resolve as a local PostgreSQL server.
- Never commit passwords, tokens, private keys, personal access tokens, session
  cookies or production connection strings. Do not put them in PR text, screenshots,
  test fixtures, terminal recordings or issue logs. Browser-exposed `VITE_*`
  variables must never contain secrets.
- `docker compose config` prints resolved values; use `config --quiet` for validation.
  Environment values are accessible to people/processes controlling Docker;
  `.env` and containers are not a production secret-management system.

The `ci-only-*` values in the workflow are public dummy credentials for a fresh
service container. They must never be reused outside disposable CI validation.
Local random credentials are also separate from production credentials. A future
production setup requires its own reviewed configuration, secrets management,
TLS, database privileges and operational controls; this repo does not provide it.

If a real secret is exposed, revoke/rotate it first. Remove it from active files
and coordinate history/log cleanup with the maintainer. Deleting it in a later
commit does not erase earlier copies. Share only redacted evidence.

## Local services and test data

Compose publishes Django (8000), Vite (5173), Mailpit web (8025) and SMTP (1025)
on `127.0.0.1` by default. PostgreSQL has no published host port and joins the
internal network. Backend/frontend/Mailpit also join the `host_access` bridge and
can make outbound connections. These boundaries do not make the stack production-safe.

Do not bind development ports to public interfaces, use tunnels or change firewall
rules without reviewing exposure. Django debug pages, development servers and
Mailpit messages can disclose sensitive information. A container's `0.0.0.0`
listener differs from publishing a host port on all interfaces.

Use synthetic fixtures, disposable test databases and reserved `.test` email
addresses. Mailpit captures SMTP locally; no external relay is configured. It can
still retain message contents visible to anyone with local access. Do not use
real recipients or production SMTP credentials. Invitation emails are not yet
implemented; manual SMTP smoke commands only validate the transport.

The local PostgreSQL named volume persists across container recreation. Do not
use `docker compose down --volumes` or volume-pruning commands for routine shutdown.
Changing POSTGRES_* values does not rewrite users/passwords in an initialized
volume. Never point pytest or exploratory migration commands at production or
shared data. See [Docker operations](docs/development/docker-compose.md).

## Application boundaries

The [approved ADR/TD decisions](docs/adr/README.md) remain the source of architectural
constraints: same-origin session authentication, HttpOnly cookies, CSRF, centralized
tenant scoping, relational integrity and future isolation tests. Django middleware
and secure-cookie defaults exist, but the PR #16 slice implements login/memberships and scoped organization metadata.
The MVP branch adds scoped catalog, inventory and sales APIs with PostgreSQL
relational constraints, atomic stock operations and price snapshots.
Composite FKs do not provide SQL row visibility/RLS. A health response or green CI does
not prove tenant isolation, authorization correctness or production security.

Do not disable CSRF, add permissive CORS, wildcard hosts or weaken authentication
to make tests pass. Future business work must not trust client-supplied organization
IDs, prices or roles, and must enforce the ADR's cross-organization boundaries.

## Dependency audit policy

The [CI guide](docs/development/ci.md#dependency-vulnerability-policy) defines the
current enforced policy. From `frontend`, the exact commands are:

```text
npm audit --omit=dev --audit-level=low
npm audit --audit-level=high
```

Production findings at any reported severity fail CI; the full tree fails for
high/critical findings. Low/moderate development alerts remain visible without
failing that threshold. This also permits new moderate development findings;
reviewers must inspect audit output and dependency changes.

The [Issue #6 baseline](docs/development/issue-6-validation.md) records nine moderate
development alerts related to minimatch, versus ten in earlier reports, and zero
production findings at that time. Counts are dated evidence, not a current guarantee.
Development dependencies execute on developer/CI machines and are not risk-free.
Review at least monthly and when dependencies change; address remaining findings
through scoped maintenance work. Do not hide alerts, run `npm audit fix --force`,
add incompatible overrides or treat a passing threshold as zero vulnerabilities.
Python security scanning and a fully locked transitive Python dependency tree
are not currently provided by CI.

## Report a possible vulnerability

Do not post secrets, personal data or exploitable reproduction details in a public
issue, PR or comment. On this repository's GitHub **Security / Advisories** page,
use **Report a vulnerability** if private reporting is enabled and the button is
available. This document does not assert that the feature is enabled.

If no private reporting option is available, open a public issue containing only
a request for the maintainer's preferred private security contact, with no technical
details, credentials or attachments. Wait for a private channel before sharing the
report. No dedicated private email address is currently documented here.
This follows [GitHub's private-reporting guidance](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

Through the agreed private channel, provide affected commit/dependency versions,
impact, minimal reproduction using synthetic data and redacted evidence. Describe
any AI assistance and validation limits. Do not test against systems or data you
are not authorized to access. Maintainer availability and remediation are not
guaranteed; coordinate disclosure without publishing sensitive details prematurely.
