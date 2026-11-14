"""Database tenant consistency for the MVP's new commercial relationships."""

from django.db import migrations

RELATIONS = [
    (
        "inventory_inventorybalance",
        "variant_id",
        "catalog_productvariant",
        "inventory_balance_tenant_fk",
    ),
    (
        "inventory_stockmovement",
        "variant_id",
        "catalog_productvariant",
        "inventory_movement_tenant_fk",
    ),
    ("inventory_stockmovement", "sale_id", "sales_sale", "inventory_movement_sale_fk"),
    ("sales_saleitem", "variant_id", "catalog_productvariant", "sale_item_variant_tenant_fk"),
    ("sales_saleitem", "sale_id", "sales_sale", "sale_item_sale_tenant_fk"),
]


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table, column, parent, name in RELATIONS:
            schema_editor.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} "
                f"FOREIGN KEY ({column}, organization_id) "
                f"REFERENCES {parent} (id, organization_id) "
                "DEFERRABLE INITIALLY DEFERRED"
            )


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table, column, parent, name in reversed(RELATIONS):
            schema_editor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_initial"), ("sales", "0001_initial")]
    operations = [migrations.RunPython(forward, reverse)]
