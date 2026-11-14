from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

from catalog.serializers import TextField
from identity.serializers import StrictSerializer
from inventory.api import BusinessView, UnitsField

from .models import Sale, SaleItem
from .services import cancel_sale, create_sale


class ItemInput(StrictSerializer):
    variant_id = serializers.UUIDField()
    quantity = UnitsField(min_value=1, max_value=10000)


class SaleInput(StrictSerializer):
    items = ItemInput(many=True, min_length=1, max_length=50)

    def validate_items(self, items):
        ids = [item["variant_id"] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each variant must occur once.")
        return items


class CancellationInput(StrictSerializer):
    reason = TextField(max_length=160)


class ItemRead(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ["id", "variant_id", "sku", "quantity", "unit_price", "subtotal"]


class SaleRead(serializers.ModelSerializer):
    items = ItemRead(many=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "creator_id",
            "created_at",
            "currency",
            "total",
            "status",
            "items",
            "cancelled_at",
            "cancelled_by_id",
            "cancellation_reason",
        ]


class SaleList(BusinessView):
    def get(self, request):
        return self.page(
            Sale.objects.filter(organization=self.organization)
            .prefetch_related(
                "items",
            )
            .order_by("-created_at", "-id"),
            SaleRead,
        )

    def post(self, request):
        serializer = SaleInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            SaleRead(create_sale(request.user, serializer.validated_data)).data, status=201
        )


class SaleDetail(BusinessView):
    def get(self, request, pk):
        sale = get_object_or_404(
            Sale.objects.filter(
                organization=self.organization,
            ).prefetch_related("items"),
            pk=pk,
        )
        return Response(SaleRead(sale).data)


class CancelView(BusinessView):
    def post(self, request, pk):
        serializer = CancellationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            SaleRead(
                cancel_sale(
                    request.user,
                    pk,
                    serializer.validated_data["reason"],
                )
            ).data
        )
