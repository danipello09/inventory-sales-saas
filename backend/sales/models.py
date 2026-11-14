import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    currency = models.CharField(max_length=3)
    total = models.DecimalField(max_digits=16, decimal_places=2)
    status = models.CharField(max_length=12, default="COMPLETED")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cancelled_sales",
    )
    cancellation_reason = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "organization"], name="sale_tenant_key"),
            models.CheckConstraint(
                condition=models.Q(total__gte=0, total__lte=99999999999999),
                name="sale_total_bounds",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["COMPLETED", "CANCELLED"]),
                name="sale_status_valid",
            ),
        ]
        indexes = [models.Index(fields=["organization", "created_at", "id"])]


class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.PROTECT)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT)
    sku = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sale", "variant"], name="sale_variant_unique"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=10000),
                name="sale_item_quantity_bounds",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0, unit_price__lte=Decimal("9999999999.99")),
                name="sale_item_price_bounds",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal=models.F("unit_price") * models.F("quantity")),
                name="sale_item_subtotal_valid",
            ),
        ]
