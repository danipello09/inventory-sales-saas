from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, OperationalError, connection, connections, transaction
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from organizations.models import Membership

from .conftest import make_product

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Real PostgreSQL constraints/locks required"
    ),
]


def test_two_admins_same_tenant_cannot_create_the_same_sku_through_http(catalog_scope):
    s = catalog_scope
    second = get_user_model().objects.create_user("second-admin@example.test", "Second-admin-729!")
    Membership.objects.create(user=second, organization=s["a"], role="ADMIN")
    other_product, _ = make_product(s["a"], s["ca"], sku="HTTP-SECOND")
    barrier = Barrier(2)

    def post_variant(user_id, product_id, color):
        try:
            client = APIClient(enforce_csrf_checks=True)
            client.force_login(get_user_model().objects.get(pk=user_id))
            csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
            thread_connection()
            barrier.wait(timeout=10)
            response = client.post(
                f"/api/v1/products/{product_id}/variants/",
                {"sku": "http-race", "price": "1.00", "color": color},
                format="json",
                HTTP_X_CSRFTOKEN=csrf,
            )
            if response.status_code == 409:
                assert response.json()["error"]["code"] == "conflict"
            return response.status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(post_variant, s["owner"].pk, s["pa"].pk, "red"),
            pool.submit(post_variant, second.pk, other_product.pk, "blue"),
        ]
        assert sorted(f.result(timeout=25) for f in futures) == [201, 409]
    assert ProductVariant.objects.filter(organization=s["a"], sku="HTTP-RACE").count() == 1
    assert not ProductVariant.objects.filter(organization=s["b"], sku="HTTP-RACE").exists()


@pytest.mark.parametrize(
    "attack",
    [
        "product_category",
        "variant_product",
        "category_parent",
        "product_parent",
        "insert_product",
        "insert_variant",
    ],
)
def test_composite_foreign_keys_reject_direct_cross_tenant_writes(catalog_scope, attack):
    s = catalog_scope
    # Avoid unrelated unique/cardinality errors hiding the composite FK violation.
    ProductVariant.objects.create(
        organization=s["a"], product=s["pa"], sku="KEPT", color="green", price=1
    )
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        if attack == "product_category":
            Product.objects.filter(pk=s["pa"].pk).update(category=s["cb"])
        elif attack == "variant_product":
            ProductVariant.objects.filter(pk=s["va"].pk).update(product=s["pb"], size="foreign")
        elif attack == "category_parent":
            Category.objects.filter(pk=s["ca"].pk).update(
                organization=s["b"], name="Moved category"
            )
        elif attack == "product_parent":
            Product.objects.filter(pk=s["pa"].pk).update(organization=s["b"], category=s["cb"])
        elif attack == "insert_product":
            make_product(s["a"], s["cb"], sku="INVALID-PARENT")
        else:
            ProductVariant.objects.create(
                organization=s["a"], product=s["pb"], sku="INVALID-TENANT", color="foreign", price=1
            )
        connection.check_constraints()
    expected = (
        "catalog_product_category_org_fk"
        if attack in ("product_category", "category_parent", "insert_product")
        else "catalog_variant_product_org_fk"
    )
    assert caught.value.__cause__.diag.constraint_name == expected
    s["pa"].refresh_from_db()
    s["va"].refresh_from_db()
    assert s["pa"].organization_id == s["va"].organization_id == s["a"].pk
    assert s["pa"].category_id == s["ca"].pk and s["va"].product_id == s["pa"].pk


@pytest.mark.parametrize(
    "change",
    ["negative_price", "nan_price", "category_name", "sku", "options", "bad_sku", "bad_options"],
)
def test_direct_database_checks_and_unique_constraints(catalog_scope, change):
    s = catalog_scope
    with pytest.raises(IntegrityError), transaction.atomic():
        if change == "negative_price":
            ProductVariant.objects.filter(pk=s["va"].pk).update(price=Decimal("-0.01"))
        elif change == "nan_price":
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE catalog_productvariant SET price = 'NaN' WHERE id = %s", [s["va"].pk]
                )
        elif change == "category_name":
            Category.objects.create(organization=s["a"], name="SHIRTS")
        elif change == "sku":
            ProductVariant.objects.create(
                organization=s["a"], product=s["pa"], sku="BASE", size="l", price=1
            )
        elif change == "options":
            ProductVariant.objects.create(
                organization=s["a"], product=s["pa"], sku="DUP-PLAIN", price=1
            )
        elif change == "bad_sku":
            ProductVariant.objects.filter(pk=s["va"].pk).update(sku="not canonical")
        else:
            ProductVariant.objects.filter(pk=s["va"].pk).update(size=" M ")
        connection.check_constraints()


def test_product_without_variants_cannot_commit_and_last_variant_cannot_be_removed(catalog_scope):
    s = catalog_scope
    with pytest.raises(IntegrityError, match="at least one variant"), transaction.atomic():
        Product.objects.create(organization=s["a"], category=s["ca"], name="Incomplete")
    assert not Product.objects.filter(name="Incomplete").exists()
    with pytest.raises(IntegrityError, match="at least one variant"), transaction.atomic():
        ProductVariant.objects.filter(pk=s["va"].pk).delete()
    assert ProductVariant.objects.filter(pk=s["va"].pk).exists()
    with pytest.raises(IntegrityError, match="at least one variant"), transaction.atomic():
        # Composite FK is valid; the old product still must not lose its last variant.
        second, _ = make_product(s["a"], s["ca"], sku="SECOND")
        ProductVariant.objects.filter(pk=s["va"].pk).update(product=second, size="m")
    assert ProductVariant.objects.filter(pk=s["va"].pk, product=s["pa"]).exists()


def test_real_postgresql_schema_declares_the_documented_constraints():
    with connection.cursor() as cursor:
        cursor.execute("""SELECT conname, condeferrable, condeferred FROM pg_constraint
                       WHERE conname IN ('catalog_product_category_org_fk',
                                         'catalog_variant_product_org_fk')""")
        assert set(cursor.fetchall()) == {
            ("catalog_product_category_org_fk", True, True),
            ("catalog_variant_product_org_fk", True, True),
        }
        cursor.execute("""SELECT tgname FROM pg_trigger WHERE tgname IN
                       ('catalog_product_requires_variant', 'catalog_variant_delete_guard',
                        'catalog_variant_move_guard') AND tgdeferrable AND tginitdeferred""")
        assert len(cursor.fetchall()) == 3


def thread_connection(isolation=None):
    conn = connections["default"]
    with conn.cursor() as cursor:
        cursor.execute("SET statement_timeout = '15s'")
        cursor.execute("SET lock_timeout = '12s'")
        if isolation:
            cursor.execute("SET default_transaction_isolation = 'repeatable read'")
    return conn


def test_concurrent_sku_collision_is_enforced_without_python_or_service_locks(catalog_scope):
    s = catalog_scope
    another, _ = make_product(s["a"], s["ca"], sku="SECOND")
    barrier = Barrier(2)

    def insert(product_id):
        try:
            thread_connection()
            barrier.wait(timeout=10)
            try:
                with transaction.atomic():
                    ProductVariant.objects.create(
                        organization_id=s["a"].pk,
                        product_id=product_id,
                        sku="RACING-SKU",
                        color="red",
                        price=Decimal("1.00"),
                    )
                return "committed"
            except IntegrityError as error:
                assert error.__cause__.diag.constraint_name == "catalog_sku_unique"
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(insert, pk) for pk in (s["pa"].pk, another.pk)]
        assert sorted(f.result(timeout=25) for f in futures) == ["committed", "rejected"]
    assert ProductVariant.objects.filter(organization=s["a"], sku="RACING-SKU").count() == 1


@pytest.mark.parametrize("repeatable_read", [False, True])
def test_competing_last_variant_removals_cannot_commit_an_empty_product(
    catalog_scope, repeatable_read
):
    s = catalog_scope
    extra = ProductVariant.objects.create(
        organization=s["a"], product=s["pa"], sku="EXTRA", color="red", price=1
    )
    barrier = Barrier(2)

    def remove(pk):
        try:
            thread_connection(isolation=repeatable_read)
            try:
                with transaction.atomic():
                    ProductVariant.objects.filter(pk=pk).delete()
                    barrier.wait(timeout=10)
                return "committed"
            except IntegrityError as error:
                assert error.__cause__.diag.constraint_name == "catalog_product_has_variant"
                return "rejected"
            except OperationalError as error:
                # A stale repeatable-read writer must abort (serialization failure).
                assert repeatable_read and error.__cause__.sqlstate == "40001"
                return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(remove, pk) for pk in (s["va"].pk, extra.pk)]
        assert sorted(f.result(timeout=25) for f in futures) == ["committed", "rejected"]
    assert ProductVariant.objects.filter(product=s["pa"]).count() == 1
