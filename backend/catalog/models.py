import uuid
from decimal import Decimal

from django.db import models
from django.db.models.functions import Lower, Trim


class CatalogRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(CatalogRecord):
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "organization", Lower("name"), name="catalog_category_name_unique"
            ),
            models.UniqueConstraint(
                fields=["id", "organization"], name="catalog_category_tenant_key"
            ),
            models.CheckConstraint(
                condition=models.Q(name=Trim("name")) & models.Q(name__regex=r"\S"),
                name="catalog_category_name_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "created_at", "id"], name="catalog_category_page")
        ]


class Product(CatalogRecord):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "organization"], name="catalog_product_tenant_key"
            ),
            models.CheckConstraint(
                condition=models.Q(name=Trim("name")) & models.Q(name__regex=r"\S"),
                name="catalog_product_name_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "created_at", "id"], name="catalog_product_page")
        ]

    @property
    def is_available(self):
        return self.is_active and self.category.is_active


class ProductVariant(CatalogRecord):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="variants")
    sku = models.CharField(max_length=64)
    size = models.CharField(max_length=40, blank=True, default="")
    color = models.CharField(max_length=40, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "organization"], name="catalog_variant_tenant_key"
            ),
            models.UniqueConstraint(fields=["organization", "sku"], name="catalog_sku_unique"),
            models.UniqueConstraint(
                fields=["product", "size", "color"], name="catalog_options_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(sku__regex=r"^[A-Z0-9]") & ~models.Q(sku__regex=r"[^A-Z0-9._-]"),
                name="catalog_sku_canonical",
            ),
            models.CheckConstraint(
                condition=models.Q(size=Lower(Trim("size")), color=Lower(Trim("color"))),
                name="catalog_options_canonical",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0, price__lte=Decimal("9999999999.99")),
                name="catalog_price_bounds",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "product", "created_at", "id"], name="catalog_variant_page"
            )
        ]

    @property
    def is_available(self):
        return self.is_active and self.product.is_available
