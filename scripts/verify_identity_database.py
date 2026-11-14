"""Verify fresh and legacy PostgreSQL schemas without touching existing databases.

Run using backend/.venv's Python (requirements include psycopg). Creates one new
Docker container, two temporary databases, a baseline clone and a local HTTP server.
Only this invocation's container/anonymous volume and server are cleaned up.
"""

import http.cookiejar
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

import psycopg


def main():
    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    workspace = Path(tempfile.mkdtemp(prefix="identity-postgres-"))
    name = "mission-identity-" + uuid.uuid4().hex[:12]
    password = secrets.token_hex(24)
    env = dict(
        os.environ,
        DATABASE_HOST="127.0.0.1",
        POSTGRES_DB="identity_fresh",
        POSTGRES_USER="mission_identity",
        POSTGRES_PASSWORD=password,
        DJANGO_SECRET_KEY=secrets.token_hex(32),
        DJANGO_DEBUG="false",
        EXPECT_DATABASE_VENDOR="postgresql",
    )
    results = []
    log = (workspace / "validation.log").open("w", encoding="utf-8")

    def run(
        label, command, *, cwd=backend, process_env=None, expected=0, contains=None
    ):
        result = subprocess.run(
            command, cwd=cwd, env=process_env or env, capture_output=True, timeout=300
        )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        output = output.replace(password, "[REDACTED]").replace(
            env["DJANGO_SECRET_KEY"], "[REDACTED]"
        )
        log.write(f"\n## {label}\n{output}\n")
        log.flush()
        assert result.returncode == expected, (
            f"{label}: exit {result.returncode}; inspect validation.log"
        )
        assert contains is None or contains in output, label
        results.append(
            {"check": label, "exit_code": result.returncode, "expected_exit": expected}
        )
        print(f"{label}: exit {result.returncode} (expected {expected})", flush=True)
        return output

    def connect(database):
        return psycopg.connect(
            host=env["DATABASE_HOST"],
            port=env["DATABASE_PORT"],
            user=env["POSTGRES_USER"],
            password=password,
            dbname=database,
            autocommit=True,
        )

    server = None
    owned_container = False
    try:
        run(
            "Create owned PostgreSQL",
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--publish",
                "127.0.0.1::5432",
                "--env",
                "POSTGRES_DB=identity_fresh",
                "--env",
                "POSTGRES_USER=mission_identity",
                "--env",
                f"POSTGRES_PASSWORD={password}",
                "--health-cmd",
                "pg_isready -U mission_identity -d identity_fresh",
                "--health-interval",
                "2s",
                "--health-retries",
                "30",
                "postgres:17.12-bookworm",
            ],
        )
        owned_container = True
        for _ in range(60):
            health = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", name]
            )
            if health.strip() == b"healthy":
                break
            time.sleep(1)
        else:
            raise RuntimeError("PostgreSQL health timeout")
        env["DATABASE_PORT"] = (
            subprocess.check_output(["docker", "port", name, "5432"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        with connect("identity_fresh") as db:
            db.execute("CREATE DATABASE identity_legacy")
            version = db.execute("SELECT version()").fetchone()[0]
            assert "PostgreSQL 17.12" in version
        baseline = workspace / "baseline"
        run(
            "Clone baseline",
            [
                "git",
                "clone",
                "--no-checkout",
                "https://github.com/danipello09/inventory-sales-saas.git",
                str(baseline),
            ],
        )
        run(
            "Pin baseline",
            [
                "git",
                "-C",
                str(baseline),
                "checkout",
                "--detach",
                "757cc5d2a0f8eee0292ecb737fd72cadea343e71",
            ],
        )
        legacy_env = dict(env, POSTGRES_DB="identity_legacy")
        run(
            "Apply actual legacy migrations",
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=baseline / "backend",
            process_env=legacy_env,
        )
        with connect("identity_legacy") as db:
            before = db.execute(
                "SELECT app, name FROM django_migrations ORDER BY app, name"
            ).fetchall()
            assert len(before) == 18
            db.execute("CREATE TABLE mission_legacy_marker (value text)")
            db.execute("INSERT INTO mission_legacy_marker VALUES ('must-survive')")
            tables_before = db.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            ).fetchall()
        run(
            "Legacy migration rejected before writes",
            [sys.executable, "manage.py", "migrate", "--noinput"],
            process_env=legacy_env,
            expected=1,
            contains="Legacy auth.User database detected",
        )
        with connect("identity_legacy") as db:
            assert (
                before
                == db.execute(
                    "SELECT app, name FROM django_migrations ORDER BY app, name"
                ).fetchall()
            )
            assert (
                tables_before
                == db.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                ).fetchall()
            )
            assert db.execute("SELECT value FROM mission_legacy_marker").fetchone() == (
                "must-survive",
            )
        results.append(
            {"check": "Legacy schema/history/data unchanged", "status": "passed"}
        )
        run(
            "Fresh custom-user migrations",
            [sys.executable, "manage.py", "migrate", "--noinput"],
        )
        run(
            "Idempotent fresh migrate",
            [sys.executable, "manage.py", "migrate", "--noinput"],
            contains="No migrations to apply",
        )
        run(
            "Reverse MVP tenant DDL on owned database",
            [sys.executable, "manage.py", "migrate", "inventory", "0002", "--noinput"],
        )
        run(
            "Reapply MVP tenant DDL",
            [sys.executable, "manage.py", "migrate", "inventory", "0003", "--noinput"],
        )
        run("Django system checks", [sys.executable, "manage.py", "check"])
        run(
            "Migration drift",
            [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
        )
        run("Ruff backend", [sys.executable, "-m", "ruff", "check", "."])
        run(
            "Real PostgreSQL tests",
            [sys.executable, "-m", "pytest", "-q"],
            contains="passed",
        )
        with connect("identity_fresh") as db:
            assert db.execute("SELECT count(*) FROM django_migrations").fetchone() == (
                27,
            )
            assert db.execute(
                "SELECT data_type FROM information_schema.columns WHERE table_name='accounts_user' AND column_name='id'"
            ).fetchone() == ("uuid",)
            assert db.execute("SELECT to_regclass('auth_user')").fetchone() == (None,)
        results.append(
            {
                "check": "Fresh schema: UUID user, 27 migrations, no auth_user",
                "status": "passed",
            }
        )

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server_env = dict(env, DJANGO_DEBUG="true")
        server = subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{port}",
                "--noreload",
            ],
            cwd=backend,
            env=server_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        base = f"http://127.0.0.1:{port}"

        def request(path, method="GET", payload=None, csrf=None, expected=200):
            headers = {"Content-Type": "application/json", "Origin": base}
            if csrf:
                headers["X-CSRFToken"] = csrf
            data = None if payload is None else json.dumps(payload).encode()
            try:
                with opener.open(
                    Request(base + path, data=data, headers=headers, method=method),
                    timeout=10,
                ) as response:
                    code, body = response.status, response.read()
            except HTTPError as error:
                code, body = error.code, error.read()
            assert code == expected, (path, method, code, expected)
            results.append({"check": f"HTTP {method} {path}", "status": code})
            print(f"HTTP {method} {path}: {code}", flush=True)
            return json.loads(body) if body else None

        for _ in range(60):
            try:
                request("/health/")
                break
            except URLError:
                assert server.poll() is None, "HTTP server exited"
                time.sleep(0.5)
        else:
            raise RuntimeError("HTTP readiness timeout")
        data = {
            "email": "http-owner@example.test",
            "password": "Real-HTTP-synthetic-729!",
            "organization_name": "HTTP Test Store",
            "currency": "COP",
        }
        request("/api/v1/auth/register/", "POST", data, expected=403)
        csrf = request("/api/v1/auth/csrf/")["csrfToken"]
        identity = request("/api/v1/auth/register/", "POST", data, csrf, expected=201)
        assert identity["membership"]["role"] == "ADMIN"
        assert request("/api/v1/auth/me/")["id"] == identity["id"]
        assert request("/api/v1/organization/")["name"] == "HTTP Test Store"
        csrf = request("/api/v1/auth/csrf/")["csrfToken"]
        assert (
            request("/api/v1/organization/", "PATCH", {"name": "Renamed HTTP"}, csrf)[
                "name"
            ]
            == "Renamed HTTP"
        )
        request("/api/v1/auth/logout/", "POST", {}, csrf, expected=204)
        request("/api/v1/auth/me/", expected=401)
        csrf = request("/api/v1/auth/csrf/")["csrfToken"]
        request(
            "/api/v1/auth/login/",
            "POST",
            {"email": data["email"], "password": data["password"]},
            csrf,
        )
        assert request("/api/v1/auth/me/")["id"] == identity["id"]
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=15)
        try:
            if owned_container:
                run(
                    "Cleanup only owned PostgreSQL/volume",
                    ["docker", "rm", "--force", "--volumes", name],
                )
        finally:
            log.close()
            (workspace / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )
            print(f"Evidence retained in {workspace}", flush=True)


if __name__ == "__main__":
    main()
