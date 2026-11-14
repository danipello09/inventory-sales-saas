import uuid

import pytest
from django.db import IntegrityError

from catalog.models import Category, Product, ProductVariant
from catalog.services import create_product

from .conftest import browser, csrf, make_product, write

pytestmark = pytest.mark.django_db


def test_decimal_upper_bound_and_canonical_sku_syntax(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    path = f"products/{s['pa'].pk}/variants/{s['va'].pk}/"
    response = write(client, path, {"price": "9999999999.99", "sku": " upper-max "}, "patch")
    assert response.status_code == 200
    assert response.json()["price"] == "9999999999.99" and response.json()["sku"] == "UPPER-MAX"
    for sku in ("", "bad space", "-bad", "a" * 65, "á", ["array"]):
        assert write(client, path, {"sku": sku}, "patch").status_code == 400


@pytest.mark.parametrize("mode", ["mismatch", "hostile_origin"])
def test_every_catalog_mutation_rejects_invalid_csrf_context(catalog_scope, mode):
    s = catalog_scope
    client = browser(s["owner"])
    token = csrf(client)
    headers = {"HTTP_X_CSRFTOKEN": "x" * 64 if mode == "mismatch" else token}
    if mode == "hostile_origin":
        headers["HTTP_ORIGIN"] = "https://hostile.example.test"
    for path in routes(s):
        method = "post" if path.endswith(("categories/", "products/", "variants/")) else "patch"
        response = getattr(client, method)("/api/v1/" + path, {}, format="json", **headers)
        assert response.status_code == 403
    assert Product.objects.count() == ProductVariant.objects.count() == 2


def product_payload(category_id, **updates):
    return {
        "category_id": str(category_id),
        "name": "New Shirt",
        "variants": [
            {"sku": "NEW-PLAIN", "price": "0"},
            {"sku": "NEW-BLUE", "size": " M ", "color": " Blue ", "price": "19.50"},
        ],
        **updates,
    }


def routes(scope):
    return [
        "categories/",
        f"categories/{scope['ca'].pk}/",
        "products/",
        f"products/{scope['pa'].pk}/",
        f"products/{scope['pa'].pk}/variants/",
        f"products/{scope['pa'].pk}/variants/{scope['va'].pk}/",
    ]


def test_admin_crud_category_product_and_variant(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    category = write(client, "categories/", {"name": " Summer "})
    assert category.status_code == 201
    assert category.json()["name"] == "Summer"
    response = write(client, "products/", product_payload(category.json()["id"]))
    assert response.status_code == 201, response.data
    product = response.json()
    pk = product["id"]
    assert uuid.UUID(pk) and product["variant_count"] == 2
    assert "variants" not in product and product["is_available"]
    assert client.get(f"/api/v1/products/{pk}/").json() == product
    listed = client.get(f"/api/v1/products/{pk}/variants/").json()
    assert listed["count"] == 2
    variants = {v["sku"]: v for v in listed["results"]}
    assert variants["NEW-PLAIN"]["price"] == "0.00"
    assert variants["NEW-BLUE"]["size"] == "m" and variants["NEW-BLUE"]["color"] == "blue"
    path = f"products/{pk}/variants/{variants['NEW-BLUE']['id']}/"
    updated = write(client, path, {"price": "20.01", "sku": " renamed "}, "patch")
    assert updated.status_code == 200 and updated.json()["price"] == "20.01"
    assert updated.json()["sku"] == "RENAMED"
    assert write(client, f"products/{pk}/", {"name": "New name"}, "patch").status_code == 200
    assert (
        write(
            client, f"categories/{category.json()['id']}/", {"name": "Renamed"}, "patch"
        ).status_code
        == 200
    )
    assert (
        write(
            client, f"products/{pk}/variants/", {"sku": "RED", "color": "red", "price": "9.99"}
        ).status_code
        == 201
    )


def test_two_tenants_are_scoped_on_every_route_and_category_assignment(catalog_scope):
    s = catalog_scope
    a, b = browser(s["owner"]), browser(s["other"])
    assert a.get("/api/v1/categories/").json()["count"] == 1
    assert b.get("/api/v1/products/").json()["results"][0]["id"] == str(s["pb"].pk)
    for path in routes(s)[1:]:
        if path == "products/":
            continue
        assert b.get("/api/v1/" + path).status_code == 404, path
    assert write(b, "products/", product_payload(s["ca"].pk)).status_code == 404
    assert (
        write(a, f"products/{s['pa'].pk}/", {"category_id": str(s["cb"].pk)}, "patch").status_code
        == 404
    )
    assert (
        write(b, f"products/{s['pa'].pk}/variants/", {"sku": "FOREIGN", "price": "1"}).status_code
        == 404
    )
    assert write(b, f"products/{s['pa'].pk}/", {"name": "Attack"}, "patch").status_code == 404
    s["pa"].refresh_from_db()
    assert s["pa"].name == "Test Product"
    # Correct organization but wrong parent still returns 404.
    another, _ = make_product(s["a"], s["ca"], sku="SECOND")
    assert a.get(f"/api/v1/products/{another.pk}/variants/{s['va'].pk}/").status_code == 404
    assert a.get(f"/api/v1/products/?category_id={s['cb'].pk}").json()["count"] == 0


def test_staff_reads_all_own_routes_but_cannot_write(catalog_scope):
    s = catalog_scope
    client = browser(s["staff"])
    for path in routes(s):
        assert client.get("/api/v1/" + path).status_code == 200
    attempts = [
        ("categories/", {"name": "Denied"}, "post"),
        (f"categories/{s['ca'].pk}/", {"name": "Denied"}, "patch"),
        ("products/", product_payload(s["ca"].pk), "post"),
        (f"products/{s['pa'].pk}/", {"name": "Denied"}, "patch"),
        (f"products/{s['pa'].pk}/variants/", {"sku": "NO", "price": "1"}, "post"),
        (f"products/{s['pa'].pk}/variants/{s['va'].pk}/", {"price": "1"}, "patch"),
    ]
    for path, payload, method in attempts:
        assert write(client, path, payload, method).status_code == 403
    assert Product.objects.filter(organization=s["a"]).count() == 1
    assert client.get(f"/api/v1/products/{s['pb'].pk}/").status_code == 404


@pytest.mark.parametrize(
    "mode",
    ["anonymous", "no_membership", "inactive_member", "suspended", "platform", "inactive_user"],
)
def test_denied_accounts_have_no_catalog_access(catalog_scope, mode):
    s = catalog_scope
    user = s["owner"]
    if mode == "anonymous":
        user = None
    elif mode == "no_membership":
        s["member"].delete()
    elif mode == "inactive_member":
        s["member"].is_active = False
        s["member"].save()
    elif mode == "suspended":
        s["a"].status = "SUSPENDED"
        s["a"].save()
    elif mode == "platform":
        user.is_superuser = True
        user.save()
    else:
        user.is_active = False
        user.save()
    client = browser(user)
    expected = 401 if mode in ("anonymous", "inactive_user") else 403
    for path in routes(s):
        assert client.get("/api/v1/" + path).status_code == expected
    assert write(client, "categories/", {"name": "Forbidden"}).status_code == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("organization_id", "foreign"),
        ("organization", "foreign"),
        ("role", "ADMIN"),
        ("id", str(uuid.uuid4())),
        ("is_superuser", True),
    ],
)
def test_mass_assignment_rejected_for_all_writers(catalog_scope, field, value):
    s = catalog_scope
    client = browser(s["owner"])
    attempts = [
        ("categories/", {"name": "Extra"}, "post"),
        (f"categories/{s['ca'].pk}/", {"name": "Extra"}, "patch"),
        ("products/", product_payload(s["ca"].pk), "post"),
        (f"products/{s['pa'].pk}/", {"name": "Extra"}, "patch"),
        (f"products/{s['pa'].pk}/variants/", {"sku": "EXTRA", "price": "1"}, "post"),
        (f"products/{s['pa'].pk}/variants/{s['va'].pk}/", {"price": "1"}, "patch"),
    ]
    for path, data, method in attempts:
        assert write(client, path, {**data, field: value}, method).status_code == 400
    s["pa"].refresh_from_db()
    assert s["pa"].name == "Test Product"


@pytest.mark.parametrize(
    "variants",
    [
        [],
        None,
        [{"sku": "X", "price": "1"}] * 51,
        [{"sku": "dup", "price": "1"}, {"sku": "DUP", "color": "red", "price": "2"}],
        [{"sku": "X", "price": "1"}, {"sku": "Y", "price": "2", "size": None, "color": ""}],
        [
            {"sku": "X", "price": "1", "size": "M", "color": "Blue"},
            {"sku": "Y", "price": "2", "size": " m ", "color": "blue"},
        ],
    ],
)
def test_product_requires_bounded_distinct_variants(catalog_scope, variants):
    s = catalog_scope
    client = browser(s["owner"])
    assert (
        write(client, "products/", product_payload(s["ca"].pk, variants=variants)).status_code
        == 400
    )
    assert Product.objects.count() == 2 and ProductVariant.objects.count() == 2
    data = product_payload(s["ca"].pk)
    data.pop("variants")
    assert write(client, "products/", data).status_code == 400


def test_late_variant_failure_rolls_back_the_entire_product(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    response = write(
        client,
        "products/",
        product_payload(
            s["ca"].pk,
            variants=[
                {"sku": "WOULD-BE-CREATED", "price": "1"},
                {"sku": s["va"].sku, "price": "2", "color": "red"},
            ],
        ),
    )
    assert response.status_code == 409
    assert not ProductVariant.objects.filter(sku="WOULD-BE-CREATED").exists()
    assert Product.objects.count() == ProductVariant.objects.count() == 2
    # Independent of serializer validation: a DB check failure rolls back earlier rows too.
    with pytest.raises(IntegrityError):
        create_product(
            s["owner"],
            {
                "category_id": s["ca"].pk,
                "name": "Rollback",
                "variants": [
                    {"sku": "FIRST-ROW", "price": "1"},
                    {"sku": "SECOND-ROW", "price": "-1", "color": "red"},
                ],
            },
        )
    assert not Product.objects.filter(name="Rollback").exists()


@pytest.mark.parametrize(
    "price",
    [-1, 1.25, True, "-1", "-0.00", "1.001", "NaN", "Infinity", "1e2", "10000000000.00", "", None],
)
def test_invalid_money_is_rejected(catalog_scope, price):
    s = catalog_scope
    client = browser(s["owner"])
    response = write(
        client, f"products/{s['pa'].pk}/variants/{s['va'].pk}/", {"price": price}, "patch"
    )
    assert response.status_code == 400
    s["va"].refresh_from_db()
    assert str(s["va"].price) == "12.50"


def test_category_sku_and_variant_uniqueness_survives_deactivation(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    assert write(client, "categories/", {"name": " shirts "}).status_code == 409
    assert (
        write(client, f"categories/{s['ca'].pk}/", {"is_active": False}, "patch").status_code == 200
    )
    assert write(client, "categories/", {"name": "Shirts"}).status_code == 409
    assert (
        write(client, f"categories/{s['ca'].pk}/", {"is_active": True}, "patch").status_code == 200
    )
    assert (
        write(
            client, f"products/{s['pa'].pk}/variants/{s['va'].pk}/", {"is_active": False}, "patch"
        ).status_code
        == 200
    )
    assert (
        write(
            client, f"products/{s['pa'].pk}/variants/", {"sku": "base", "price": "1", "size": "l"}
        ).status_code
        == 409
    )
    assert (
        write(
            client, f"products/{s['pa'].pk}/variants/", {"sku": "OTHER", "price": "1"}
        ).status_code
        == 409
    )


def test_deactivation_is_effective_without_rewriting_descendants(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    assert (
        write(client, f"categories/{s['ca'].pk}/", {"is_active": False}, "patch").status_code == 200
    )
    assert not client.get(f"/api/v1/products/{s['pa'].pk}/").json()["is_available"]
    assert not client.get(f"/api/v1/products/{s['pa'].pk}/variants/{s['va'].pk}/").json()[
        "is_available"
    ]
    s["pa"].refresh_from_db()
    s["va"].refresh_from_db()
    assert s["pa"].is_active and s["va"].is_active
    assert write(client, "products/", product_payload(s["ca"].pk)).status_code == 409
    assert (
        write(
            client, f"products/{s['pa'].pk}/variants/", {"sku": "NO", "price": "1", "color": "red"}
        ).status_code
        == 409
    )
    assert (
        write(client, f"products/{s['pa'].pk}/", {"name": "Allowed metadata"}, "patch").status_code
        == 200
    )
    assert write(client, f"products/{s['pa'].pk}/", {"is_active": True}, "patch").status_code == 409
    assert client.get("/api/v1/products/?available=false").json()["count"] == 1


def test_pagination_search_and_filters_are_scoped_and_bounded(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    Category.objects.bulk_create(
        [Category(organization=s["a"], name=f"Category {i}") for i in range(22)]
    )
    response = client.get("/api/v1/categories/?page_size=2").json()
    assert response["count"] == 23 and len(response["results"]) == 2 and response["next"]
    assert client.get("/api/v1/categories/?search=SHIRTS").json()["count"] == 1
    assert client.get("/api/v1/products/?search=test&sku=base").json()["count"] == 1
    assert client.get(f"/api/v1/products/?category_id={s['cb'].pk}").json()["count"] == 0
    for query in (
        "page_size=101",
        "page_size=0",
        "page=0",
        "is_active=maybe",
        "organization_id=other",
        "category_id=bad",
        "search=" + "x" * 81,
        "page=" + "9" * 5000,
    ):
        path = "products/" if query.startswith("category_id") else "categories/"
        assert client.get("/api/v1/" + path + "?" + query).status_code == 400, query[:40]
    assert client.get("/api/v1/categories/?page=9999").status_code == 404
    assert client.get(f"/api/v1/products/{s['pa'].pk}/variants/?size=&color=").json()["count"] == 1


def test_csrf_methods_invalid_json_and_empty_patch(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    for path in routes(s):
        method = "post" if path.endswith(("categories/", "products/", "variants/")) else "patch"
        response = getattr(client, method)("/api/v1/" + path, {}, format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_failed"
        assert write(client, path, {}, "delete").status_code == 405
        assert write(client, path, {}, "put").status_code == 405
    for path in (
        f"categories/{s['ca'].pk}/",
        f"products/{s['pa'].pk}/",
        f"products/{s['pa'].pk}/variants/{s['va'].pk}/",
    ):
        assert write(client, path, {}, "patch").status_code == 400
        assert write(client, path, {}, "post").status_code == 405
    from .conftest import csrf

    response = client.post(
        "/api/v1/products/", "{bad", content_type="application/json", HTTP_X_CSRFTOKEN=csrf(client)
    )
    assert response.status_code == 400
    assert write(client, "categories/", [], "post").status_code == 400
