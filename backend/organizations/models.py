import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Trim


class Organization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    class Currency(models.TextChoices):
        COP = "COP", "Colombian peso"
        USD = "USD", "US dollar"
        EUR = "EUR", "Euro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    currency = models.CharField(max_length=3, choices=Currency, default=Currency.COP)
    status = models.CharField(max_length=9, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name=Trim("name")) & ~models.Q(name=""),
                name="organizations_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "SUSPENDED"]),
                name="organizations_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(currency__in=["COP", "USD", "EUR"]),
                name="organizations_currency_valid",
            ),
        ]


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        STAFF = "STAFF", "Staff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    role = models.CharField(max_length=5, choices=Role)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["ADMIN", "STAFF"]),
                name="memberships_role_valid",
            ),
        ]
