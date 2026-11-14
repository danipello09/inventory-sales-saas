# Safe development cutover to accounts.User

The approved identity design, onboarding and Phase 2 evidence from PRs #15, #13
and #14 are integrated in main (`efa2602`). PR #16 implements the first backend
slice. This procedure creates a **new Compose project and new PostgreSQL volume**;
it is not a migration of the old environment and does not copy its users/data.

## Rules before starting

- Keep the Phase 2 checkout, project and PostgreSQL volume intact. Never run the
  feature checkout against that volume. Do not use plain `docker compose up` from
  this checkout: compose.yaml's default project name belongs to the old environment.
- Keep the custom migrate guard. Its rejection is intentional, not an instruction
  to use `--fake`, edit old migrations or delete a volume.
- Use the new-project procedure below, even if the old project is stopped. Changing
  only POSTGRES_DB or its password does not create a new volume.
- This is loopback-only development. The [public exposure gates](identity-public-exposure.md)
  remain open. Do not use production data or credentials.

## Create a new environment once

Use a separate checkout/worktree of the implementation branch. Git, Docker Linux
with Compose v2+ and Python 3.12 are required; this startup script uses only the
Python standard library, so host Node and pip dependencies are unnecessary.
Run from that checkout's root. **Windows PowerShell:**

```powershell
py -3.12 scripts/start_identity_sandbox.py
```

**Linux Bash:**

```bash
python3.12 scripts/start_identity_sandbox.py
```

The command does the following, failing if any mandatory check fails:

1. Generates an unpredictable `identity-sandbox-<id>` project name and verifies
   neither that project nor its `<project>_postgres_data` volume exists.
2. Writes fresh random development credentials and four distinct loopback ports
   to a private sandbox.env outside the repository, under
   `~/.inventory-sales-saas/sandboxes/<project>/`. It never reads/copies the old .env.
3. Passes the exact compose.yaml, project directory, new env file and project name
   explicitly to every Compose invocation. It checks the resolved model in memory
   for the new volume, private DB and loopback publications; no credentials are printed.
4. Builds backend/frontend, starts all four services and waits for healthchecks.
5. Inspects the database container's project label and actual volume mount to prove
   it uses the newly named volume; then applies migrations only there.
6. Checks real PostgreSQL, the new user schema and 20 migrations, runs Django check,
   and prints URLs and the path to manifest.json. The new stack stays running.

The private manifest records project/volume names, URLs and the exact Compose argv.
Keep sandbox.env and manifest.json outside Git; protect them like local credentials.
On Linux the script requests owner-only file/directory permissions; on Windows
access also depends on the user's existing filesystem ACLs. This is not a
production secrets store. Re-running the startup command creates another fresh
sandbox: **do not use it to resume an existing one**.

## Resume, inspect and stop that same sandbox

Read the printed manifest and use its exact `compose_argv` prefix. The following
template works in PowerShell and Bash after replacing every placeholder with
the corresponding manifest value. Do not substitute the original project/env:

```text
docker compose --project-directory "<new-checkout>" -f "<new-checkout>/compose.yaml" --env-file "<private-sandbox-directory>/sandbox.env" --project-name "identity-sandbox-<id>" ps
```

Keep that prefix unchanged and replace only the final `ps` with one command:

| Purpose | Command after the exact prefix |
| --- | --- |
| Check services | `ps` |
| Read backend logs (review before sharing) | `logs --tail=80 backend` |
| Pause without removing containers/data | `stop` |
| Resume the same environment | `start --wait` |
| Remove containers/network, retain PostgreSQL | `down` |
| Start again with retained data | `up -d --wait --wait-timeout 120` |
| Run backend tests on its separate test database | `exec -T backend python -m pytest -q` |
| Check pending migrations | `exec -T backend python manage.py makemigrations --check --dry-run` |

Never add `--volumes` for routine shutdown. Never prune volumes. The old and new
projects can coexist because published host ports differ. PostgreSQL has no host
port. Use the manifest's backend/frontend/Mailpit URLs, not the old default URLs.
The frontend still has its starter screen; authentication is currently an API.

## Reproduce the cutover and HTTP checks without keeping test resources

From the same checkout, run the alternative verification mode:

```powershell
py -3.12 scripts/start_identity_sandbox.py --verify
```

```bash
python3.12 scripts/start_identity_sandbox.py --verify
```

This follows the same startup path with another new project/volume and synthetic
fixtures. It uses real HTTP/cookies to register two organizations, check CSRF,
rename only the owner's organization, deny STAFF writes and foreign-object access,
restart only the new backend, and verify sessions survive restart while logout
invalidates a copied session without affecting the other organization. It then
removes **only the newly created verification project/volumes** in finally. The
original project/volume is never attached or used. Redacted logs/results remain
in a temporary identity-sandbox-* directory; that verification manifest is not a
persistent development environment and must not be reused.

The separate `scripts/verify_identity_database.py`, run with the backend venv's
Python, verifies all PostgreSQL tests and rejects a real old schema created in a
different disposable database from the baseline migrations. The old schema's
tables/history/marker must remain unchanged. See [backend verification](identity-backend.md)
and the [hardening report](pr-16-hardening.md) for actual results.

## Existing data and rollback

This cutover does not preserve old users in the new database. A future data transfer
needs an explicitly approved, tested conversion plan; it is not part of PR #16.
To keep using the old environment, use its original checkout and project unchanged.
There is no need to reverse migrations, rename tables, fake history, delete data
or alter approved architectural decisions. Human review is still required before merge.
