"""Refuse an unsafe default-user to custom-user transition before migration work."""

from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as DjangoMigrateCommand
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder


def check_legacy_schema(connection):
    tables = set(connection.introspection.table_names())
    applied = MigrationRecorder(connection).applied_migrations()
    if ("auth_user" in tables and "accounts_user" not in tables) or (
        ("admin", "0001_initial") in applied and ("accounts", "0001_initial") not in applied
    ):
        raise CommandError(
            "Legacy auth.User database detected. No migration was applied. "
            "Keep the existing database/volume and Phase 2 checkout intact. "
            "Use a NEW isolated database/Compose project for accounts.User. "
            "A data-preserving transition needs a separately reviewed plan; "
            "do not fake migrations or delete the old volume."
        )


class Command(DjangoMigrateCommand):
    def handle(self, *args, **options):
        check_legacy_schema(connections[options["database"]])
        return super().handle(*args, **options)
