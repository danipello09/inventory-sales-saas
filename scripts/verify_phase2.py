"""Verify a clean Phase 2 clone using only newly owned, disposable Docker resources.

Run with Python 3.12 from any directory. Logs/cloned source stay in a temporary
directory for inspection; only this invocation's Compose resources are removed.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="757cc5d2a0f8eee0292ecb737fd72cadea343e71")
    args = parser.parse_args()
    workspace = Path(tempfile.mkdtemp(prefix="inventory-phase2-"))
    clone = workspace / "source"
    project = "mission-phase2-" + uuid.uuid4().hex[:12]
    log = (workspace / "validation.log").open("w", encoding="utf-8")
    results = []
    env = os.environ.copy()
    env.update(
        {
            "POSTGRES_DB": "phase2_review",
            "POSTGRES_USER": "phase2_review",
            "POSTGRES_PASSWORD": secrets.token_hex(24),
            "DJANGO_SECRET_KEY": secrets.token_hex(32),
            "DJANGO_DEBUG": "true",
            "BACKEND_PORT": str(free_port()),
            "FRONTEND_PORT": str(free_port()),
            "MAILPIT_WEB_PORT": str(free_port()),
            "MAILPIT_SMTP_PORT": str(free_port()),
        }
    )

    def run(label, command):
        started = time.monotonic()
        result = subprocess.run(command, cwd=workspace, env=env, capture_output=True)
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        for key in ("POSTGRES_PASSWORD", "DJANGO_SECRET_KEY"):
            output = output.replace(env[key], "[REDACTED]")
        log.write(f"\n## {label}\n{output}\n")
        log.flush()
        results.append(
            {
                "check": label,
                "exit_code": result.returncode,
                "seconds": round(time.monotonic() - started, 2),
            }
        )
        print(f"{label}: exit {result.returncode}", flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect redacted validation.log")
        return output

    run(
        "Clone from origin",
        [
            "git",
            "clone",
            "--no-checkout",
            "https://github.com/danipello09/inventory-sales-saas.git",
            str(clone),
        ],
    )
    run(
        "Checkout exact revision",
        ["git", "-C", str(clone), "checkout", "--detach", args.ref],
    )
    run("Clean clone status", ["git", "-C", str(clone), "status", "--porcelain"])
    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(clone),
        "--project-name",
        project,
        "--env-file",
        str(clone / ".env.example"),
    ]
    # Refuse to reuse resources, even though the randomized collision is unlikely.
    existing = subprocess.check_output(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"label=com.docker.compose.project={project}",
        ]
    ).strip()
    volumes = subprocess.check_output(
        [
            "docker",
            "volume",
            "ls",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={project}",
        ]
    ).strip()
    assert not existing and not volumes

    def backend(label, code):
        return run(
            label,
            compose
            + ["exec", "-T", "backend", "python", "manage.py", "shell", "-c", code],
        )

    def http(label, port, path, expected=200, contains=None):
        try:
            with urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as response:
                status, body = response.status, response.read().decode()
        except HTTPError as error:
            status, body = error.code, error.read().decode()
        assert status == expected, (label, status)
        assert contains is None or contains in body, label
        results.append({"check": label, "status": status})
        print(f"{label}: HTTP {status}", flush=True)
        return body

    try:
        run("Compose configuration", compose + ["config", "--quiet"])
        run("Build both images", compose + ["build"])
        run(
            "Start four healthy services",
            compose + ["up", "-d", "--wait", "--wait-timeout", "120"],
        )
        run(
            "Apply migrations",
            compose
            + ["exec", "-T", "backend", "python", "manage.py", "migrate", "--noinput"],
        )
        backend(
            "Real PostgreSQL",
            "from django.db import connection; connection.ensure_connection(); "
            "assert connection.vendor == 'postgresql'; c=connection.cursor(); "
            "c.execute('SELECT current_database(), version()'); print(c.fetchone()); c.close()",
        )
        for command in (
            ["python", "manage.py", "check"],
            ["python", "-m", "ruff", "check", "."],
            ["python", "-m", "pytest", "-q"],
            ["python", "manage.py", "makemigrations", "--check", "--dry-run"],
        ):
            run(
                "Backend " + " ".join(command),
                compose + ["exec", "-T", "backend"] + command,
            )
        for command in (
            ["npm", "run", "lint"],
            ["npm", "test"],
            ["npm", "run", "build"],
            ["npm", "audit", "--omit=dev", "--audit-level=low"],
            ["npm", "audit", "--audit-level=high"],
        ):
            run(
                "Frontend " + " ".join(command),
                compose + ["exec", "-T", "frontend"] + command,
            )
        http(
            "Django health", env["BACKEND_PORT"], "/health/", contains='"status": "ok"'
        )
        http("Frontend HTML", env["FRONTEND_PORT"], "/", contains="/src/main.tsx")
        http(
            "Frontend transformed module",
            env["FRONTEND_PORT"],
            "/src/App.tsx",
            contains="Phase 2",
        )
        http(
            "Django API via Vite proxy",
            env["FRONTEND_PORT"],
            "/api/v1/",
            expected=404,
            contains="Django",
        )
        http("Mailpit web", env["MAILPIT_WEB_PORT"], "/")
        subject = "Phase 2 isolated check " + project
        backend(
            "SMTP delivery",
            "from django.core.mail import send_mail; "
            f"assert send_mail({subject!r}, 'Synthetic test only.', 'sender@inventory.test', "
            "['recipient@inventory.test']) == 1",
        )
        messages = json.loads(
            http(
                "Mailpit captured message", env["MAILPIT_WEB_PORT"], "/api/v1/messages"
            )
        )
        assert any(message["Subject"] == subject for message in messages["messages"])
        backend(
            "Create persistence marker",
            "from django.db import connection; c=connection.cursor(); "
            "c.execute('CREATE TABLE mission_persistence_probe (value text NOT NULL)'); "
            "c.execute(\"INSERT INTO mission_persistence_probe VALUES ('owned-by-mission')\"); c.close()",
        )
        before = run(
            "Database ID before recreation", compose + ["ps", "-q", "db"]
        ).strip()
        run(
            "Recreate only owned database container",
            compose + ["up", "-d", "--force-recreate", "db"],
        )
        run(
            "Wait after recreation",
            compose + ["up", "-d", "--wait", "--wait-timeout", "120"],
        )
        after = run(
            "Database ID after recreation", compose + ["ps", "-q", "db"]
        ).strip()
        assert before != after
        backend(
            "Persisted data and migrations",
            "from django.db import connection; c=connection.cursor(); "
            "c.execute('SELECT value FROM mission_persistence_probe'); "
            "assert c.fetchone() == ('owned-by-mission',); "
            "c.execute('SELECT count(*) FROM django_migrations'); assert c.fetchone()[0] == 18; "
            "c.execute('DROP TABLE mission_persistence_probe'); c.close()",
        )
        # Inspect the resolved model in memory only, never print environment values.
        model = json.loads(
            subprocess.check_output(compose + ["config", "--format", "json"], env=env)
        )
        assert set(model["services"]) == {"backend", "frontend", "db", "mailpit"}
        assert not model["services"]["db"].get("ports")
        assert all(
            p["host_ip"] == "127.0.0.1"
            for s in model["services"].values()
            for p in s.get("ports", [])
        )
        results.append(
            {
                "check": "Security topology: loopback ports, DB private",
                "status": "passed",
            }
        )
    finally:
        # Only a generated mission project in our new temporary clone is eligible.
        assert project.startswith("mission-phase2-") and clone.parent == workspace
        try:
            run(
                "Cleanup owned containers and volumes",
                compose + ["down", "--volumes", "--remove-orphans"],
            )
        finally:
            (workspace / "results.json").write_text(
                json.dumps(
                    {
                        "ref": args.ref,
                        "project": project,
                        "workspace": str(workspace),
                        "results": results,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            log.close()
            print(f"Evidence retained in {workspace}", flush=True)


if __name__ == "__main__":
    main()
