from functools import wraps

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from identity.errors import Conflict
from identity.services import organization_for_user

from .models import Category, Product, ProductVariant

UNIQUE_CONSTRAINTS = {
    "catalog_category_name_unique",
    "catalog_sku_unique",
    "catalog_options_unique",
}


def atomic_catalog_write(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            with transaction.atomic():
                return function(*args, **kwargs)
        except IntegrityError as error:
            constraint = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
            sqlite_unique = "UNIQUE constraint failed" in str(error) and ("catalog_" in str(error))
            if constraint in UNIQUE_CONSTRAINTS or sqlite_unique:
                raise Conflict(
                    "The catalog name, SKU or variant identity is already reserved."
                ) from error
            raise

    return wrapped


def scoped(model, organization, pk, **extra):
    return get_object_or_404(model.objects.filter(organization=organization), pk=pk, **extra)


def active_category(organization, pk):
    category = scoped(Category, organization, pk)
    if not category.is_active:
        raise Conflict("The category is inactive.")
    return category


def require_available(product):
    if not product.is_available:
        raise Conflict("The product or its category is inactive.")


@atomic_catalog_write
def create_category(user, data):
    organization = organization_for_user(user, admin=True, lock=True)
    return Category.objects.create(organization=organization, **data)


@atomic_catalog_write
def update_category(user, pk, data):
    organization = organization_for_user(user, admin=True, lock=True)
    category = scoped(Category, organization, pk)
    for key, value in data.items():
        setattr(category, key, value)
    category.save()
    return category


@atomic_catalog_write
def create_product(user, data):
    organization = organization_for_user(user, admin=True, lock=True)
    category = active_category(organization, data["category_id"])
    variants = data["variants"]
    if not 1 <= len(variants) <= 50:
        raise ValidationError({"variants": ["Supply 1–50 variants."]})
    product = Product.objects.create(
        organization=organization,
        category=category,
        name=data["name"],
        is_active=data.get("is_active", True),
    )
    for variant in variants:
        ProductVariant.objects.create(organization=organization, product=product, **variant)
    return product


@atomic_catalog_write
def update_product(user, pk, data):
    organization = organization_for_user(user, admin=True, lock=True)
    product = scoped(Product, organization, pk)
    if "category_id" in data:
        product.category = active_category(organization, data["category_id"])
    if data.get("is_active") is True and not product.category.is_active:
        raise Conflict("An active category is required to reactivate the product.")
    for key in ("name", "is_active"):
        if key in data:
            setattr(product, key, data[key])
    product.save()
    return product


@atomic_catalog_write
def create_variant(user, product_id, data):
    organization = organization_for_user(user, admin=True, lock=True)
    product = scoped(Product, organization, product_id)
    require_available(product)
    return ProductVariant.objects.create(organization=organization, product=product, **data)


@atomic_catalog_write
def update_variant(user, product_id, pk, data):
    organization = organization_for_user(user, admin=True, lock=True)
    product = scoped(Product, organization, product_id)
    variant = scoped(ProductVariant, organization, pk, product=product)
    if data.get("is_active") is True:
        require_available(product)
    for key, value in data.items():
        setattr(variant, key, value)
    variant.save()
    return variant
