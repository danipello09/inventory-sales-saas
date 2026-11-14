# Contributing

This repository is in Phase 2: architecture and infrastructure. Start with the
[project README](README.md), [approved decisions](docs/adr/README.md) and the issue's
acceptance criteria. Business designs are not authorization to implement features
outside your selected issue.

For the custom-user identity branch, use only the [new-project cutover](docs/development/identity-cutover.md).
The default Compose project belongs to the old Phase 2 database. All Compose
checks below require the exact new-project prefix from the sandbox manifest;
never execute them against the original/default project or volume.

## Choose an issue and prepare the environment

Choose a scoped task from the repository's
[issues](https://github.com/danipello09/inventory-sales-saas/issues). Check its state,
existing PRs and discussion to avoid duplicating work. For unclear scope, propose a
small concrete change before expanding it. Security reports follow
[SECURITY.md](SECURITY.md), not a public issue containing sensitive details.

Use the README's [Docker quick start](README.md#quick-start-with-docker-compose).
For host tools, follow [standalone development](docs/development/README.md).
Use Python 3.12 and Node 22 to match CI. Keep `.env` local and use synthetic data.
Run `git status` before switching branches; preserve unrelated local changes and
never discard them to make a command work.

## Branches and everyday Git

Create each task branch from current `main`. With a clean working tree, these
commands work in PowerShell and Bash:

```text
git switch main
git pull --ff-only origin main
git switch -c docs/issue-7-onboarding
git status --short --branch
```

The branch above is the example for Issue #7; choose your own issue's name instead
of reusing an existing branch. Contributors without write access should fork the
repository, use their fork as `origin`, and fetch the original repository as
`upstream`; replace the base-update command with `git pull --ff-only upstream main`.
Open the PR from your fork's branch to this repository's `main`.

Use `<type>/issue-<number>-<short-kebab-case-description>`, for example:

| Prefix | Use |
| --- | --- |
| `docs/` | Documentation, such as `docs/issue-7-onboarding` |
| `chore/` | Tooling/infrastructure, such as `chore/issue-6-github-actions` |
| `fix/` | A scoped bug fix |
| `feat/` | An approved feature in an implementation phase |

Edit within the issue's scope. Inspect changes before staging; stage explicit
paths instead of accidentally including generated output or local configuration:

```text
git diff
git add README.md CONTRIBUTING.md
git diff --cached
git diff --cached --check
git commit -m "docs: add onboarding and contribution guides"
git push -u origin docs/issue-7-onboarding
```

Replace the file list with your actual reviewed files. `git diff` does not show
untracked file contents: also inspect `git status` and new files. Keep commits
coherent and use conventional subjects: `docs:`, `ci:`, `chore:`, `fix:` or `feat:`
followed by a concise description of the outcome. An optional scope is fine,
for example `docs(onboarding): clarify database setup`. Never include credentials.

Fetch regularly and inspect divergence with `git log --oneline main..HEAD` and
`git diff main...HEAD` after updating your local main reference. When the base
changes, integrate it deliberately. For a shared branch, prefer coordinating a
merge of `origin/main` over rewriting someone else's history. Resolve conflicts
file by file, review the result and re-run affected checks. Rebase only your own
work with coordination; never force-push shared branches or `main`. If you must
update an agreed rebased personal branch, use `--force-with-lease`, not `--force`.

Do not combine dependency upgrades, formatting churn, business implementation and
unrelated fixes into a documentation task. Put additional work in its own issue/PR.

## Validate before requesting review

With the new sandbox running and migrated, use the exact Compose prefix from its
manifest before each suffix below (PowerShell or Bash). These are suffixes, not
complete shell commands. Stop and investigate any nonzero exit code:

```text
config --quiet
exec -T backend python manage.py check
exec -T backend python -m ruff check .
exec -T backend python -m pytest -q
exec -T frontend npm run lint
exec -T frontend npm test
exec -T frontend npm run build
exec -T frontend npm audit --omit=dev --audit-level=low
exec -T frontend npm audit --audit-level=high
```

Run `git diff --check` separately in the checkout. Never replace the prefix with the
old/default Compose project. The [cutover guide](docs/development/identity-cutover.md)
provides the complete manifest-specific command template.

Build images first using the README; `npm ci` is part of the frontend image build.
For package changes, commit `package.json` and `package-lock.json` together and
follow the [frontend volume refresh procedure](docs/development/docker-compose.md#editing-and-dependency-changes).
The [CI guide](docs/development/ci.md) contains standalone equivalents and the
isolated PostgreSQL/migration commands. Changes to migrations require the
PostgreSQL integration check, not only SQLite smoke tests.

For documentation-only work, verify internal links/anchors, file paths, shell
syntax, commands and claimed behavior against the source; validate Compose with
explicit dummy values as described in the CI guide. Record exactly what you ran.
It is acceptable to say that local application tests were not re-run when no code
changed; do not call them passed based on earlier evidence. All five remote jobs
still run on documentation PRs. Do not add artificial tests to inflate coverage.

PowerShell does not stop automatically after failed native commands. For automation,
check `$LASTEXITCODE` and throw/exit on failure. Use Bash syntax only in Bash and
PowerShell syntax only in PowerShell; shared command blocks are labeled `text`.

## Open a draft PR

Push the branch and open a **draft** PR targeting `main`. Keep the existing
[PR template](.github/PULL_REQUEST_TEMPLATE.md) sections:

- **Related issue:** use `Closes #<number>` when the PR completes that issue.
  GitHub closes it upon merge to the default branch; do not close it manually
  while delivery/review is still pending. Use `Refs #<number>` for partial work.
- **Scope:** explain the concrete problem, resulting behavior and affected files.
  Include limitations or meaningful tradeoffs; avoid an account of every edit.
- **Validation:** list exact commands, runtime/database context, exit codes and
  actual outcomes. Only tick boxes when supported by evidence.
- **Evidence:** link the run for the current commit, relevant logs or a sanitized
  validation report. Distinguish AI-assisted inspection from human review.

Example scope: "New contributors could not find a complete setup sequence.
This PR adds a root quick start and links detailed Docker/CI instructions,
while identifying business features as planned. No runtime behavior changes."

Never attach `.env`, database dumps, private emails, access tokens or resolved
Compose configuration. Redact logs before sharing. Report checks not run or
blocked explicitly, including the reason.

## Review, CI and merge

Read the PR's **Checks** tab, select **Quality checks**, then expand the first
failed step in the relevant job. The five check names are **Django checks**,
**React checks**, **PostgreSQL integration**, **Docker Compose validation** and
**npm dependency audit**. The [CI guide](docs/development/ci.md#reading-pr-results-and-logs)
explains their exact responsibilities and thresholds. Queued, skipped or cancelled
jobs are not proof of success. Review the latest head commit, not an old green run.

Reviewers should check scope, correctness, security implications, evidence and
documentation. Describe the concrete problem and its impact; separate blocking
findings from suggestions. Authors should acknowledge each finding, make a fix or
explain their reasoning, and push focused follow-up commits. Request re-review
and resolve threads once addressed; a disagreement needs discussion, not silent
dismissal. New commits may cancel earlier CI runs; wait for the current results.

Keep the PR in draft until the work and evidence are complete. Mark it ready for
human review when appropriate. Merge is allowed only after the acceptance criteria
are met, all five latest checks pass, review concerns/conflicts are resolved and
the maintainer has accepted the change under the repository's current rules.
A green run alone is not approval or permission to merge. Do not bypass protections,
change branch rules or merge someone else's work without authorization.

## Definition of done

- The issue's scoped behavior/documentation is complete and independently reviewable.
- A focused branch/PR contains no unrelated changes, secrets or generated files.
- Relevant local validation and the five remote jobs have documented real results.
- Current setup, security and architectural implications are documented accurately.
- Review concerns are addressed and remaining limitations/debt are disclosed.
- Human acceptance is obtained before merge; a draft PR is delivery for review,
  not completion of the maintainer's merge decision.

Owner learning notes are in the [Spanish study guide](docs/study/development-workflow-es.md).
