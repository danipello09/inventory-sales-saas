from django.db.models import Value
from django.db.models.functions import Coalesce
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from catalog.models import ProductVariant
from catalog.serializers import TextField
from catalog.views import CatalogPagination
from identity.serializers import StrictSerializer
from identity.services import organization_for_user
from identity.views import IdentityAPIView

from .models import StockMovement
from .services import adjust_stock


class UnitsField(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail("invalid")
        return super().to_internal_value(data)


class Adjustment(StrictSerializer):
    variant_id = serializers.UUIDField()
    delta = UnitsField(min_value=-10000, max_value=10000)
    reason = TextField(max_length=160)

    def validate_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("Delta must be nonzero.")
        return value


class BusinessView(IdentityAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.organization = organization_for_user(request.user)

    def page(self, query, reader):
        allowed = {"page", "page_size"}
        if set(self.request.query_params) - allowed:
            raise ValidationError("Unknown pagination parameter.")
        for key in allowed:
            if key in self.request.query_params:
                raw = self.request.query_params[key]
                if (
                    len(raw) > 7
                    or not raw.isascii()
                    or not raw.isdigit()
                    or not 1 <= int(raw) <= (100 if key == "page_size" else 1000000)
                ):
                    raise ValidationError("Invalid pagination parameter.")
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(query, self.request, view=self)
        return paginator.get_paginated_response(reader(page, many=True).data)


class InventoryRead(serializers.ModelSerializer):
    variant_id = serializers.UUIDField(source="id")
    product_name = serializers.CharField(source="product.name")
    quantity = serializers.IntegerField()
    is_available = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = ProductVariant
        fields = [
            "variant_id",
            "sku",
            "product_name",
            "size",
            "color",
            "price",
            "quantity",
            "is_available",
        ]


class InventoryList(BusinessView):
    def get(self, request):
        query = (
            ProductVariant.objects.filter(organization=self.organization)
            .select_related(
                "product__category",
            )
            .annotate(quantity=Coalesce("inventorybalance__quantity", Value(0)))
            .order_by("sku", "id")
        )
        return self.page(query, InventoryRead)


class AdjustmentView(BusinessView):
    def post(self, request):
        serializer = Adjustment(data=request.data)
        serializer.is_valid(raise_exception=True)
        balance = adjust_stock(request.user, serializer.validated_data)
        return Response(
            {"variant_id": str(balance.variant_id), "quantity": balance.quantity}, status=201
        )


class MovementRead(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = ["id", "variant_id", "delta", "reason", "actor_id", "sale_id", "created_at"]


class MovementList(BusinessView):
    def get(self, request):
        return self.page(
            StockMovement.objects.filter(
                organization=self.organization,
            ).order_by("-created_at", "-id"),
            MovementRead,
        )
