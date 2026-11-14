from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import IntegrityError, connection, connections, transaction

from catalog.models import ProductVariant
from catalog.tests.conftest import browser, csrf, make_product, write
from identity.errors import Conflict
from inventory.models import InventoryBalance, StockMovement
from inventory.services import adjust_stock
from sales.models import Sale, SaleItem
from sales.services import create_sale

pytestmark = pytest.mark.django_db(transaction=True)


def adjustment(s, delta=10):
    return {"variant_id": str(s["va"].pk), "delta": delta, "reason": "Physical count"}


def order(s, quantity=3):
    return {"items": [{"variant_id": str(s["va"].pk), "quantity": quantity}]}


def test_real_api_flow_snapshots_and_idempotent_cancellation(catalog_scope):
    s = catalog_scope
    admin, staff = browser(s["owner"]), browser(s["staff"])
    assert admin.get("/api/v1/inventory/").json()["results"][0]["quantity"] == 0
    assert write(admin, "inventory/adjustments/", adjustment(s)).status_code == 201
    response = write(staff, "sales/", order(s))
    assert response.status_code == 201
    sale = response.json()
    assert sale["total"] == "37.50" and sale["items"][0]["unit_price"] == "12.50"
    assert admin.get("/api/v1/inventory/").json()["results"][0]["quantity"] == 7
    ProductVariant.objects.filter(pk=s["va"].pk).update(price=Decimal("99.00"))
    detail = staff.get(f"/api/v1/sales/{sale['id']}/").json()
    assert detail["items"][0]["unit_price"] == "12.50" and detail["total"] == "37.50"
    assert len(admin.get("/api/v1/inventory/movements/").json()["results"]) == 2
    assert staff.get("/api/v1/sales/").json()["count"] == 1
    url = f"sales/{sale['id']}/cancel/"
    assert write(staff, url, {"reason": "No permission"}).status_code == 403
    for _ in range(2):
        assert write(admin, url, {"reason": "Entry error"}).json()["status"] == "CANCELLED"
    assert InventoryBalance.objects.get(variant=s["va"]).quantity == 10
    assert StockMovement.objects.count() == 3


def test_tenant_isolation_and_staff_denial(catalog_scope):
    s = catalog_scope
    a, b, staff = browser(s["owner"]), browser(s["other"]), browser(s["staff"])
    assert write(staff, "inventory/adjustments/", adjustment(s)).status_code == 403
    assert write(b, "inventory/adjustments/", adjustment(s)).status_code == 404
    assert write(b, "sales/", order(s)).status_code == 404
    assert write(a, "inventory/adjustments/", adjustment(s)).status_code == 201
    sale = write(a, "sales/", order(s)).json()
    assert b.get("/api/v1/sales/").json()["count"] == 0
    assert b.get(f"/api/v1/sales/{sale['id']}/").status_code == 404
    assert write(b, f"sales/{sale['id']}/cancel/", {"reason": "Foreign"}).status_code == 404
    assert b.get("/api/v1/inventory/movements/").json()["count"] == 0
    rows = b.get("/api/v1/inventory/").json()["results"]
    assert all(row["variant_id"] != str(s["va"].pk) for row in rows)


def test_adjustment_bounds_and_atomic_insufficient_sale(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    assert write(client, "inventory/adjustments/", adjustment(s, -1)).status_code == 409
    assert not InventoryBalance.objects.exists() and not StockMovement.objects.exists()
    write(client, "inventory/adjustments/", adjustment(s, 10))
    write(client, "inventory/adjustments/", adjustment(s, -2))
    assert InventoryBalance.objects.get(variant=s["va"]).quantity == 8
    _, variant = make_product(s["a"], s["ca"], sku="NO-STOCK")
    payload = {"items": [*order(s)["items"], {"variant_id": str(variant.pk), "quantity": 1}]}
    assert write(client, "sales/", payload).status_code == 409
    assert not Sale.objects.exists() and not SaleItem.objects.exists()
    assert StockMovement.objects.count() == 2
    assert InventoryBalance.objects.get(variant=s["va"]).quantity == 8


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"items": []},
        {"items": [{"variant_id": "bad", "quantity": 1}]},
        {"items": [{"quantity": -1}]},
    ],
)
def test_invalid_sale_json_rejected(catalog_scope, payload):
    client = browser(catalog_scope["owner"])
    if payload is None:
        response = client.post(
            "/api/v1/sales/", "null", content_type="application/json", HTTP_X_CSRFTOKEN=csrf(client)
        )
    else:
        response = write(client, "sales/", payload)
    assert response.status_code == 400
    assert not Sale.objects.exists()


@pytest.mark.parametrize("delta", [0, True, 1.5, "2", 10001])
def test_invalid_adjustments(catalog_scope, delta):
    assert (
        write(
            browser(catalog_scope["owner"]),
            "inventory/adjustments/",
            adjustment(catalog_scope, delta),
        ).status_code
        == 400
    )


def test_csrf_privileges_inactive_and_history_methods(catalog_scope):
    s = catalog_scope
    client = browser(s["owner"])
    for path, payload in [("sales/", order(s)), ("inventory/adjustments/", adjustment(s))]:
        assert client.post("/api/v1/" + path, payload, format="json").status_code == 403
        assert (
            write(client, path, {**payload, "organization_id": str(s["a"].pk)}).status_code == 400
        )
        assert (
            client.post(
                "/api/v1/" + path,
                "{",
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf(client),
            ).status_code
            == 400
        )
    assert (
        client.patch(
            "/api/v1/inventory/movements/", {}, format="json", HTTP_X_CSRFTOKEN=csrf(client)
        ).status_code
        == 405
    )
    write(client, "inventory/adjustments/", adjustment(s))
    s["ca"].is_active = False
    s["ca"].save()
    assert write(client, "sales/", order(s)).status_code == 409
    assert InventoryBalance.objects.get(variant=s["va"]).quantity == 10
    s["a"].status = "SUSPENDED"
    s["a"].save()
    assert client.get("/api/v1/inventory/").status_code == 403
    assert write(client, "sales/", order(s)).status_code == 403
    assert browser().get("/api/v1/sales/").status_code == 401


postgres = pytest.mark.skipif(connection.vendor != "postgresql", reason="Real PostgreSQL required")


@postgres
@pytest.mark.parametrize(
    "target", ["balance", "movement", "item_variant", "item_sale", "movement_sale"]
)
def test_postgres_composite_tenant_foreign_keys(catalog_scope, target):
    s = catalog_scope
    adjust_stock(s["owner"], {**adjustment(s), "variant_id": s["va"].pk})
    sale = create_sale(s["owner"], {"items": [{"variant_id": s["va"].pk, "quantity": 1}]})
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        if target == "balance":
            InventoryBalance.objects.filter(variant=s["va"]).update(organization=s["b"])
        elif target == "movement":
            StockMovement.objects.filter(sale__isnull=True).update(organization=s["b"])
        elif target == "item_variant":
            sale.items.update(variant=s["vb"])
        elif target == "item_sale":
            other = Sale.objects.create(
                organization=s["b"], creator=s["other"], currency="COP", total=0
            )
            sale.items.update(sale=other)
        else:
            other = Sale.objects.create(
                organization=s["b"], creator=s["other"], currency="COP", total=0
            )
            StockMovement.objects.filter(sale=sale).update(sale=other)
        connection.check_constraints()
    assert caught.value.__cause__.diag.constraint_name in {
        "inventory_balance_tenant_fk",
        "inventory_movement_tenant_fk",
        "sale_item_variant_tenant_fk",
        "sale_item_sale_tenant_fk",
        "inventory_movement_sale_fk",
    }


@postgres
@pytest.mark.parametrize("operation", ["sell_last", "first_adjustment"])
def test_concurrent_stock_operations(catalog_scope, operation):
    s = catalog_scope
    if operation == "sell_last":
        adjust_stock(s["owner"], {**adjustment(s, 1), "variant_id": s["va"].pk})
    barrier = Barrier(2)

    def execute():
        try:
            from accounts.models import User

            user = User.objects.get(pk=s["owner"].pk)
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout='12s'")
            barrier.wait(timeout=10)
            try:
                if operation == "sell_last":
                    create_sale(user, {"items": [{"variant_id": s["va"].pk, "quantity": 1}]})
                else:
                    adjust_stock(user, {**adjustment(s, 1), "variant_id": s["va"].pk})
                return "ok"
            except Conflict:
                return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(f.result(timeout=25) for f in [pool.submit(execute), pool.submit(execute)])
    if operation == "sell_last":
        assert results == ["conflict", "ok"]
        assert InventoryBalance.objects.get(variant=s["va"]).quantity == 0
        assert Sale.objects.count() == 1 and StockMovement.objects.count() == 2
    else:
        assert results == ["ok", "ok"]
        assert InventoryBalance.objects.get(variant=s["va"]).quantity == 2
        assert StockMovement.objects.count() == 2
