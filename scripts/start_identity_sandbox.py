"""Start a NEW identity Compose project/volume; never reuse the Phase 2 environment.

Default: retain the new sandbox and print a manifest path with explicit commands.
--verify: exercise real session/CSRF/tenant HTTP requests, then remove only the
resources created by this invocation. No existing volume is attached or removed.
Requires Python 3.12 and Docker Linux; host Python dependencies are not needed.
"""

import argparse
import copy
import http.cookiejar
import json
import os
import secrets
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify HTTP and clean up only this new sandbox",
    )
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Include catalog HTTP checks with --verify",
    )
    args = parser.parse_args()
    if args.catalog and not args.verify:
        parser.error("--catalog requires --verify")
    root = Path(__file__).resolve().parents[1]
    project = "identity-sandbox-" + uuid.uuid4().hex[:12]
    if args.verify:
        state = Path(tempfile.mkdtemp(prefix="identity-sandbox-"))
    else:
        state = Path.home() / ".inventory-sales-saas" / "sandboxes" / project
        state.mkdir(mode=0o700, parents=True, exist_ok=False)
    volume = project + "_postgres_data"
    env_file = state / "sandbox.env"
    manifest_path = state / "manifest.json"
    ports = {}
    # Reserve all four together to guarantee distinct selections, then release for Docker.
    reservations = []
    try:
        for key in (
            "BACKEND_PORT",
            "FRONTEND_PORT",
            "MAILPIT_WEB_PORT",
            "MAILPIT_SMTP_PORT",
        ):
            sock = socket.socket()
            reservations.append(sock)
            sock.bind(("127.0.0.1", 0))
            ports[key] = str(sock.getsockname()[1])
    finally:
        for sock in reservations:
            sock.close()
    values = {
        "POSTGRES_DB": "identity_sandbox",
        "POSTGRES_USER": "identity_sandbox",
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "DJANGO_SECRET_KEY": secrets.token_hex(32),
        "DJANGO_DEBUG": "true",
        **ports,
    }
    env_file.write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8"
    )
    env_file.chmod(0o600)
    env = dict(os.environ, **values)
    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(root),
        "-f",
        str(root / "compose.yaml"),
        "--env-file",
        str(env_file),
        "--project-name",
        project,
    ]
    results = []
    log = (state / "validation.log").open("w", encoding="utf-8")
    owned = False
    retained = False

    def run(label, arguments):
        result = subprocess.run(
            compose + arguments, env=env, capture_output=True, timeout=600
        )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        for key in ("POSTGRES_PASSWORD", "DJANGO_SECRET_KEY"):
            output = output.replace(values[key], "[REDACTED]")
        log.write(f"\n## {label}\n{output}\n")
        log.flush()
        require(
            result.returncode == 0,
            f"{label}: exit {result.returncode}; inspect validation.log",
        )
        results.append({"check": label, "exit_code": result.returncode})
        print(f"{label}: exit {result.returncode}", flush=True)
        return output

    def backend(label, code):
        return run(
            label, ["exec", "-T", "backend", "python", "manage.py", "shell", "-c", code]
        )

    base = f"http://127.0.0.1:{ports['BACKEND_PORT']}"

    class Browser:
        def __init__(self, cookies=None):
            self.cookies = cookies or http.cookiejar.CookieJar()
            self.opener = build_opener(HTTPCookieProcessor(self.cookies))

        def request(self, path, *, method="GET", payload=None, csrf=None, expected=200):
            headers = {"Content-Type": "application/json", "Origin": base}
            if csrf:
                headers["X-CSRFToken"] = csrf
            data = None if payload is None else json.dumps(payload).encode()
            try:
                with self.opener.open(
                    Request(
                        base + "/api/v1/" + path,
                        data=data,
                        headers=headers,
                        method=method,
                    ),
                    timeout=15,
                ) as response:
                    status, body = response.status, response.read()
                    content_type = response.headers.get_content_type()
            except HTTPError as error:
                status, body = error.code, error.read()
                content_type = error.headers.get_content_type()
            require(
                status == expected,
                f"HTTP {method} {path}: {status}, expected {expected}",
            )
            results.append({"check": f"HTTP {method} {path}", "status": status})
            print(f"HTTP {method} {path}: {status}", flush=True)
            if not body:
                return None
            if content_type == "application/json":
                return json.loads(body)
            require(status == 404, "Unexpected non-JSON API response")
            return None  # Unregistered routes use Django's normal HTML 404 response.

        def token(self):
            return self.request("auth/csrf/")["csrfToken"]

    try:
        containers = subprocess.check_output(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label=com.docker.compose.project={project}",
            ]
        )
        volumes = subprocess.check_output(
            ["docker", "volume", "ls", "-q"], text=True
        ).splitlines()
        require(
            not containers.strip() and volume not in volumes,
            "Refusing to reuse existing resources",
        )
        run("Compose config (explicit new env file)", ["config", "--quiet"])
        model = json.loads(
            subprocess.check_output(compose + ["config", "--format", "json"], env=env)
        )
        require(model["name"] == project, "Unexpected project")
        require(
            model["volumes"]["postgres_data"]["name"] == volume,
            "Unexpected volume name",
        )
        require(
            not model["volumes"]["postgres_data"].get("external"),
            "External volumes forbidden",
        )
        require(
            not model["services"]["db"].get("ports"), "Database host port forbidden"
        )
        require(
            all(
                p["host_ip"] == "127.0.0.1"
                for service in model["services"].values()
                for p in service.get("ports", [])
            ),
            "Non-loopback service exposure",
        )
        run("Build isolated backend/frontend", ["build", "backend", "frontend"])
        # Unique project and volume were verified absent; cleanup is scoped to them.
        owned = True
        run(
            "Start four healthy services",
            ["up", "-d", "--wait", "--wait-timeout", "120"],
        )
        db_id = subprocess.check_output(
            compose + ["ps", "-q", "db"], env=env, text=True
        ).strip()
        inspection = json.loads(subprocess.check_output(["docker", "inspect", db_id]))[
            0
        ]
        require(
            inspection["Config"]["Labels"]["com.docker.compose.project"] == project,
            "Database belongs to another project",
        )
        require(
            any(
                m.get("Name") == volume
                and m["Destination"] == "/var/lib/postgresql/data"
                for m in inspection["Mounts"]
            ),
            "Database did not mount the new named volume",
        )
        run(
            "Migrate only the fresh sandbox",
            ["exec", "-T", "backend", "python", "manage.py", "migrate", "--noinput"],
        )
        backend(
            "Verify new PostgreSQL schema",
            "from django.db import connection; "
            "connection.ensure_connection(); assert connection.vendor == 'postgresql'; "
            "c=connection.cursor(); c.execute('SELECT count(*) FROM django_migrations'); "
            "assert c.fetchone()[0] == 27; c.execute(\"SELECT to_regclass('auth_user')\"); "
            "assert c.fetchone()[0] is None; c.close()",
        )
        run(
            "Django system check",
            ["exec", "-T", "backend", "python", "manage.py", "check"],
        )
        manifest = {
            "project": project,
            "volume": volume,
            "compose_file": str(root / "compose.yaml"),
            "env_file": str(env_file),
            "compose_argv": compose,
            "urls": {
                "backend": base,
                "frontend": f"http://127.0.0.1:{ports['FRONTEND_PORT']}",
                "mailpit": f"http://127.0.0.1:{ports['MAILPIT_WEB_PORT']}",
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Manifest (keep private env file): {manifest_path}", flush=True)
        for service, url in manifest["urls"].items():
            print(f"{service}: {url}", flush=True)
        if args.verify:
            a, b = Browser(), Browser()
            password = "Sandbox-only-synthetic-729!"

            def register(browser, email, organization):
                payload = {
                    "email": email,
                    "password": password,
                    "organization_name": organization,
                }
                browser.request(
                    "auth/register/", method="POST", payload=payload, expected=403
                )
                return browser.request(
                    "auth/register/",
                    method="POST",
                    payload=payload,
                    csrf=browser.token(),
                    expected=201,
                )

            identity_a = register(a, "owner-a@example.test", "Tenant A")
            identity_b = register(b, "owner-b@example.test", "Tenant B")
            org_a = identity_a["membership"]["organization"]["id"]
            org_b = identity_b["membership"]["organization"]["id"]
            require(org_a != org_b, "Tenants must differ")
            a.request(
                "organization/",
                method="PATCH",
                payload={"name": "No CSRF"},
                expected=403,
            )
            a.request("auth/logout/", method="POST", payload={}, expected=403)
            a.request(
                "auth/login/",
                method="POST",
                payload={"email": "owner-a@example.test", "password": password},
                expected=403,
            )
            require(
                a.request("auth/me/")["id"] == identity_a["id"],
                "Failed requests changed session",
            )
            a.request(
                "organization/",
                method="PATCH",
                payload={"name": "Renamed A"},
                csrf=a.token(),
            )
            a.request(
                "organization/",
                method="PATCH",
                payload={"name": "Cross-tenant", "id": org_b},
                csrf=a.token(),
                expected=400,
            )
            a.request(f"organization/{org_b}/", expected=404)
            require(
                b.request("organization/")["name"] == "Tenant B", "Other tenant mutated"
            )
            backend(
                "Create only synthetic sandbox STAFF",
                "from accounts.models import User; "
                "from organizations.models import Membership; owner=User.objects.get(email='owner-a@example.test'); "
                f"staff=User.objects.create_user('staff-a@example.test', {password!r}); "
                "Membership.objects.create(user=staff, organization=owner.membership.organization, role='STAFF')",
            )
            staff = Browser()
            staff.request(
                "auth/login/",
                method="POST",
                payload={"email": "staff-a@example.test", "password": password},
                csrf=staff.token(),
            )
            require(
                staff.request("organization/")["id"] == org_a, "STAFF read wrong tenant"
            )
            staff.request(
                "organization/",
                method="PATCH",
                payload={"name": "STAFF bypass"},
                csrf=staff.token(),
                expected=403,
            )
            staff.request(f"organization/{org_b}/", expected=404)
            run("Restart only new backend (retain sessions)", ["restart", "backend"])
            run(
                "Wait for new backend",
                ["up", "-d", "--wait", "--wait-timeout", "120", "backend"],
            )
            replay = Browser()
            for cookie in a.cookies:
                replay.cookies.set_cookie(copy.copy(cookie))
            require(
                replay.request("auth/me/")["id"] == identity_a["id"],
                "Session did not survive restart",
            )
            require(
                replay.request("organization/")["name"] == "Renamed A",
                "Wrong persisted organization",
            )
            require(
                staff.request("organization/")["id"] == org_a,
                "STAFF session did not persist",
            )
            a.request(
                "auth/logout/", method="POST", payload={}, csrf=a.token(), expected=204
            )
            replay.request("auth/me/", expected=401)
            require(
                b.request("auth/me/")["id"] == identity_b["id"],
                "Logout affected other user",
            )
            require(
                b.request("organization/")["name"] == "Tenant B", "Other tenant changed"
            )
            require(
                staff.request("organization/")["name"] == "Renamed A",
                "STAFF mutated organization",
            )
            if args.catalog:
                a.request(
                    "auth/login/",
                    method="POST",
                    payload={"email": "owner-a@example.test", "password": password},
                    csrf=a.token(),
                )
                a.request(
                    "categories/",
                    method="POST",
                    payload={"name": "Shirts"},
                    expected=403,
                )
                category = a.request(
                    "categories/",
                    method="POST",
                    payload={"name": " Shirts "},
                    csrf=a.token(),
                    expected=201,
                )
                data = {
                    "category_id": category["id"],
                    "name": "Catalog shirt",
                    "variants": [
                        {"sku": "plain", "price": "12.50"},
                        {
                            "sku": "blue-m",
                            "size": "M",
                            "color": "Blue",
                            "price": "14.00",
                        },
                    ],
                }
                product = a.request(
                    "products/",
                    method="POST",
                    payload=data,
                    csrf=a.token(),
                    expected=201,
                )
                require(
                    product["variant_count"] == 2, "Product missing initial variants"
                )
                page = a.request(f"products/{product['id']}/variants/?page_size=1")
                require(
                    page["count"] == 2 and len(page["results"]) == 1 and page["next"],
                    "Unbounded or incomplete variants",
                )
                require(
                    page["results"][0]["price"] == "12.50",
                    "Monetary value not a decimal string",
                )
                b.request(f"products/{product['id']}/", expected=404)
                b.request(
                    "products/",
                    method="POST",
                    payload=data,
                    csrf=b.token(),
                    expected=404,
                )
                require(
                    b.request("products/")["count"] == 0, "Cross-tenant catalog leak"
                )
                staff.request(f"products/{product['id']}/")
                staff.request(
                    f"products/{product['id']}/",
                    method="PATCH",
                    payload={"name": "Forbidden"},
                    csrf=staff.token(),
                    expected=403,
                )
                a.request(
                    f"products/{product['id']}/variants/",
                    method="POST",
                    payload={"sku": "red", "color": "Red", "price": "1.20"},
                    csrf=a.token(),
                    expected=201,
                )
                a.request(
                    "products/",
                    method="POST",
                    payload={
                        **data,
                        "variants": [
                            {"sku": "rollback-first", "price": "1"},
                            {"sku": "PLAIN", "color": "red", "price": "1"},
                        ],
                    },
                    csrf=a.token(),
                    expected=409,
                )
                require(
                    a.request("products/")["count"] == 1, "Partial product persisted"
                )
                a.request(
                    f"categories/{category['id']}/",
                    method="PATCH",
                    payload={"is_active": False},
                    csrf=a.token(),
                )
                require(
                    not a.request(f"products/{product['id']}/")["is_available"],
                    "Inactive category did not affect availability",
                )
                fresh_category = a.request("categories/", method="POST", payload={"name": "MVP"},
                                           csrf=a.token(), expected=201)
                demo = a.request("products/", method="POST", csrf=a.token(), expected=201,
                                 payload={"name": "MVP demo", "category_id": fresh_category["id"],
                                          "variants": [{"sku": "MVP-DEMO", "price": "12.50"}]})
                variant = a.request(f"products/{demo['id']}/variants/")["results"][0]
                adjustment = {"variant_id": variant["id"], "delta": 10, "reason": "Opening stock"}
                a.request("inventory/adjustments/", method="POST", payload=adjustment, expected=403)
                staff.request("inventory/adjustments/", method="POST", payload=adjustment,
                              csrf=staff.token(), expected=403)
                b.request("inventory/adjustments/", method="POST", payload=adjustment,
                          csrf=b.token(), expected=404)
                result = a.request("inventory/adjustments/", method="POST", payload=adjustment,
                                   csrf=a.token(), expected=201)
                require(result["quantity"] == 10, "Opening balance wrong")
                order = {"items": [{"variant_id": variant["id"], "quantity": 3}]}
                b.request("sales/", method="POST", payload=order, csrf=b.token(), expected=404)
                sale = staff.request("sales/", method="POST", payload=order,
                                     csrf=staff.token(), expected=201)
                require(sale["total"] == "37.50", "Sale snapshot/total wrong")
                inventory = a.request("inventory/")["results"]
                require(next(row for row in inventory if row["variant_id"] == variant["id"])["quantity"] == 7,
                        "Stock not decremented to seven")
                require(a.request("inventory/movements/")["count"] == 2, "Missing stock history")
                require(a.request(f"sales/{sale['id']}/")["total"] == "37.50", "Sale detail wrong")
                b.request(f"sales/{sale['id']}/", expected=404)
                require(b.request("sales/")["count"] == 0, "Sales leaked across tenants")
                require(b.request("inventory/movements/")["count"] == 0, "History leaked")
                results.append({"check": "MVP real HTTP: 10 minus 3 equals 7; STAFF sale; tenant isolation",
                                "status": "passed"})
        else:
            retained = True
            print(
                "Sandbox retained. Reuse ONLY compose_argv from manifest.json for stop/start/exec.",
                flush=True,
            )
    finally:
        try:
            if owned and not retained:
                require(
                    project.startswith("identity-sandbox-") and volume not in volumes,
                    "Unsafe cleanup refused",
                )
                run(
                    "Cleanup only newly owned sandbox",
                    ["down", "--volumes", "--remove-orphans"],
                )
        finally:
            log.close()
            (state / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )
            print(f"Evidence: {state / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
