"""PostgreSQL tenant FKs and deferred product/variant cardinality invariant.

SQLite deliberately omits these backend-specific guarantees; API smoke tests alone
must not be presented as evidence of database-level tenant/cardinality integrity.
"""

from django.db import migrations

FORWARD = """
ALTER TABLE catalog_product ADD CONSTRAINT catalog_product_category_org_fk
  FOREIGN KEY (category_id, organization_id)
  REFERENCES catalog_category (id, organization_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE catalog_productvariant ADD CONSTRAINT catalog_variant_product_org_fk
  FOREIGN KEY (product_id, organization_id)
  REFERENCES catalog_product (id, organization_id) DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION catalog_assert_variant(target uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM catalog_product WHERE id = target)
     AND NOT EXISTS (SELECT 1 FROM catalog_productvariant WHERE product_id = target) THEN
    RAISE EXCEPTION 'A product requires at least one variant'
      USING ERRCODE = '23514', CONSTRAINT = 'catalog_product_has_variant';
  END IF;
END;
$$;

CREATE FUNCTION catalog_product_variant_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM catalog_assert_variant(NEW.id);
  RETURN NULL;
END;
$$;

CREATE FUNCTION catalog_removed_variant_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- A real row version serializes competing removals, including repeatable read.
  -- Do not change the business timestamp merely to acquire this serialization.
  UPDATE catalog_product SET updated_at = updated_at WHERE id = OLD.product_id;
  PERFORM catalog_assert_variant(OLD.product_id);
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER catalog_product_requires_variant
  AFTER INSERT OR UPDATE ON catalog_product DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION catalog_product_variant_guard();
CREATE CONSTRAINT TRIGGER catalog_variant_delete_guard
  AFTER DELETE ON catalog_productvariant DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION catalog_removed_variant_guard();
CREATE CONSTRAINT TRIGGER catalog_variant_move_guard
  AFTER UPDATE OF product_id ON catalog_productvariant DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION catalog_removed_variant_guard();
"""

REVERSE = """
DROP TRIGGER catalog_variant_move_guard ON catalog_productvariant;
DROP TRIGGER catalog_variant_delete_guard ON catalog_productvariant;
DROP TRIGGER catalog_product_requires_variant ON catalog_product;
DROP FUNCTION catalog_removed_variant_guard();
DROP FUNCTION catalog_product_variant_guard();
DROP FUNCTION catalog_assert_variant(uuid);
ALTER TABLE catalog_productvariant DROP CONSTRAINT catalog_variant_product_org_fk;
ALTER TABLE catalog_product DROP CONSTRAINT catalog_product_category_org_fk;
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(forward, reverse)]
