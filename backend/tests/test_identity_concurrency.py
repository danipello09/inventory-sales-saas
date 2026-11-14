"""Actual committed transactions and separate PostgreSQL connections, without mocks."""

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from rest_framework.test import APIClient

from organizations.models import Membership, Organization

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Requires PostgreSQL row locks"),
]
User = get_user_model()
PASSWORD = "Concurrent-real-requests-729!"


def bounded_connection():
    with connections["default"].cursor() as cursor:
        cursor.execute("SET statement_timeout = '15s'")
        cursor.execute("SET lock_timeout = '12s'")
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


def test_concurrent_registration_commits_exactly_one_complete_identity():
    barrier = Barrier(2)

    def register(email):
        try:
            client = APIClient(enforce_csrf_checks=True)
            csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
            bounded_connection()
            barrier.wait(timeout=10)
            response = client.post(
                "/api/v1/auth/register/",
                {
                    "email": email,
                    "password": PASSWORD,
                    "organization_name": "Race Store",
                },
                format="json",
                HTTP_X_CSRFTOKEN=csrf,
            )
            me = client.get("/api/v1/auth/me/")
            return response.status_code, me.status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(register, email) for email in ("race@example.test", "RACE@EXAMPLE.TEST")
        ]
        results = [future.result(timeout=25) for future in futures]
    assert sorted(results) == [(201, 200), (409, 401)]
    assert User.objects.count() == Organization.objects.count() == Membership.objects.count() == 1
    membership = Membership.objects.select_related("user", "organization").get()
    assert membership.role == "ADMIN" and membership.user.email == "race@example.test"
    assert membership.organization.name == "Race Store"


def wait_for_database_lock(pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
            row = cursor.fetchone()
        if row and row[0] == "Lock":
            return
        time.sleep(0.02)
    pytest.fail("Request did not block on the protected PostgreSQL row")


@pytest.mark.parametrize("change", ["role", "membership_active", "organization_status"])
def test_waiting_update_rechecks_committed_authorization_change(change):
    user = User.objects.create_user("locked@example.test", PASSWORD)
    organization = Organization.objects.create(name="Protected Store")
    member = Membership.objects.create(user=user, organization=organization, role="ADMIN")
    other = Organization.objects.create(name="Other Tenant")
    pid_queue = Queue()

    def rename():
        try:
            client = APIClient(enforce_csrf_checks=True)
            client.force_login(User.objects.get(pk=user.pk))
            csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
            pid = bounded_connection()
            pid_queue.put(pid)
            response = client.patch(
                "/api/v1/organization/",
                {"name": "Forbidden rename"},
                format="json",
                HTTP_X_CSRFTOKEN=csrf,
            )
            return response.status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as workers:
        with transaction.atomic():
            if change == "organization_status":
                locked = Organization.objects.select_for_update().get(pk=organization.pk)
                locked.status = "SUSPENDED"
                locked.save(update_fields=["status"])
            else:
                locked = Membership.objects.select_for_update().get(pk=member.pk)
                if change == "role":
                    locked.role = "STAFF"
                    locked.save(update_fields=["role"])
                else:
                    locked.is_active = False
                    locked.save(update_fields=["is_active"])
            future = workers.submit(rename)
            wait_for_database_lock(pid_queue.get(timeout=10))
        # The committed revocation/suspension must be visible after the lock wait.
        assert future.result(timeout=20) == 403
    organization.refresh_from_db()
    other.refresh_from_db()
    assert organization.name == "Protected Store" and other.name == "Other Tenant"
