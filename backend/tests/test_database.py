"""Exercise the configured database, including pytest's migration/test DB lifecycle."""

import os

import pytest
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


@pytest.mark.django_db
def test_database_connection_and_migrations():
    connection.ensure_connection()
    expected_vendor = os.environ.get("EXPECT_DATABASE_VENDOR")
    if expected_vendor:
        assert connection.vendor == expected_vendor
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
    assert ("sessions", "0001_initial") in MigrationRecorder(connection).applied_migrations()
