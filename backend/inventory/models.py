import uuid

from django.conf import settings
from django.db import models


class InventoryBalance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    variant = models.OneToOneField("catalog.ProductVariant", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0, quantity__lte=2147483647),
                name="inventory_quantity_bounds",
            )
        ]


class StockMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT)
    delta = models.IntegerField()
    reason = models.CharField(max_length=160)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sale = models.ForeignKey("sales.Sale", null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(delta=0),
                name="inventory_nonzero_movement",
            )
        ]
        indexes = [models.Index(fields=["organization", "created_at", "id"])]
