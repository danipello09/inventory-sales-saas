from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from organizations.models import Membership, Organization

PASSWORD = "Catalog-real-tests-729!"


def make_product(organization, category, *, sku="BASE", name="Test Product"):
    with transaction.atomic():
        product = Product.objects.create(organization=organization, category=category, name=name)
        variant = ProductVariant.objects.create(
            organization=organization, product=product, sku=sku, price=Decimal("12.50")
        )
    return product, variant


@pytest.fixture
def catalog_scope():
    User = get_user_model()
    a, b = (
        Organization.objects.create(name="Tenant A"),
        Organization.objects.create(name="Tenant B"),
    )
    owner = User.objects.create_user("catalog-a@example.test", PASSWORD)
    other = User.objects.create_user("catalog-b@example.test", PASSWORD)
    staff = User.objects.create_user("catalog-staff@example.test", PASSWORD)
    member = Membership.objects.create(user=owner, organization=a, role="ADMIN")
    Membership.objects.create(user=other, organization=b, role="ADMIN")
    Membership.objects.create(user=staff, organization=a, role="STAFF")
    ca = Category.objects.create(organization=a, name="Shirts")
    cb = Category.objects.create(organization=b, name="Shirts")
    pa, va = make_product(a, ca)
    pb, vb = make_product(b, cb)  # Same SKU is legal across organizations.
    return {
        "a": a,
        "b": b,
        "owner": owner,
        "other": other,
        "staff": staff,
        "member": member,
        "ca": ca,
        "cb": cb,
        "pa": pa,
        "pb": pb,
        "va": va,
        "vb": vb,
    }


def browser(user=None):
    client = APIClient(enforce_csrf_checks=True)
    if user:
        client.force_login(user)
    return client


def csrf(client):
    return client.get("/api/v1/auth/csrf/").json()["csrfToken"]


def write(client, path, payload, method="post"):
    return getattr(client, method)(
        "/api/v1/" + path, payload, format="json", HTTP_X_CSRFTOKEN=csrf(client)
    )
