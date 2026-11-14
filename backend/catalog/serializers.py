import re

from rest_framework import serializers

from identity.serializers import StrictSerializer

from .models import Category, Product, ProductVariant


class TextField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class ActiveField(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid", input=data)
        return data


class OptionField(TextField):
    def run_validation(self, data=serializers.empty):
        return super().run_validation("" if data is None else data)

    def to_internal_value(self, data):
        return super().to_internal_value(data).lower()


class PriceField(serializers.DecimalField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r"[0-9]{1,10}(\.[0-9]{1,2})?", data):
            raise serializers.ValidationError(
                "Use a nonnegative decimal string with at most 2 decimals."
            )
        return super().to_internal_value(data)


class SKUField(TextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data).upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,63}", value):
            raise serializers.ValidationError(
                "Use 1–64 ASCII letters/digits, dots, underscores or hyphens."
            )
        return value


class CategoryWrite(StrictSerializer):
    name = TextField(max_length=120)
    is_active = ActiveField(default=True)


class VariantWrite(StrictSerializer):
    sku = SKUField(max_length=64)
    price = PriceField(max_digits=12, decimal_places=2, min_value=0)
    size = OptionField(max_length=40, allow_blank=True, default="")
    color = OptionField(max_length=40, allow_blank=True, default="")
    is_active = ActiveField(default=True)


class ProductWrite(StrictSerializer):
    category_id = serializers.UUIDField()
    name = TextField(max_length=160)
    is_active = ActiveField(default=True)


class ProductCreate(ProductWrite):
    variants = VariantWrite(many=True, min_length=1, max_length=50)

    def validate_variants(self, variants):
        skus = [item["sku"] for item in variants]
        options = [(item["size"], item["color"]) for item in variants]
        if len(set(skus)) != len(skus) or len(set(options)) != len(options):
            raise serializers.ValidationError(
                "Repeated SKU or size/color identity in this product."
            )
        return variants


class CategoryRead(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "is_active", "created_at", "updated_at"]


class ProductRead(serializers.ModelSerializer):
    variant_count = serializers.IntegerField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "category_id",
            "name",
            "is_active",
            "is_available",
            "variant_count",
            "created_at",
            "updated_at",
        ]


class VariantRead(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product_id",
            "sku",
            "size",
            "color",
            "price",
            "is_active",
            "is_available",
            "created_at",
            "updated_at",
        ]
