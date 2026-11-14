from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from identity.services import organization_for_user
from identity.views import IdentityAPIView

from . import services
from .models import Category, Product, ProductVariant
from .serializers import (
    CategoryRead,
    CategoryWrite,
    ProductCreate,
    ProductRead,
    ProductWrite,
    VariantRead,
    VariantWrite,
)


class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CatalogView(IdentityAPIView):
    model = None
    reader = None
    writer = None
    filters = set()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.organization = organization_for_user(
            request.user, admin=request.method in ("POST", "PATCH")
        )

    def queryset(self):
        query = self.model.objects.filter(organization=self.organization)
        if self.model is Product:
            query = query.select_related("category").annotate(variant_count=Count("variants"))
        if self.model is ProductVariant:
            query = query.select_related("product__category")
        return query

    def get_item(self, pk):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(self.queryset(), pk=pk)

    def data(self, request, *, partial=False):
        serializer = self.writer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if partial and not serializer.validated_data:
            raise ValidationError("Supply at least one allowed field.")
        return serializer.validated_data

    def filtered(self, request):
        allowed = {"page", "page_size", "search", "is_active", "available"} | self.filters
        unknown = set(request.query_params) - allowed
        if unknown:
            raise ValidationError({key: ["Unknown filter."] for key in unknown})
        for key in ("page", "page_size"):
            if key in request.query_params:
                value = request.query_params[key]
                if (
                    len(value) > 7
                    or not value.isascii()
                    or not value.isdigit()
                    or not 1 <= int(value) <= (100 if key == "page_size" else 1000000)
                ):
                    raise ValidationError({key: ["Invalid positive pagination value."]})
        query = self.queryset()
        for key in ("is_active", "available"):
            if key not in request.query_params:
                continue
            raw = request.query_params[key]
            if raw not in ("true", "false"):
                raise ValidationError({key: ["Use true or false."]})
            active = Q(is_active=True)
            if key == "available" and self.model is Product:
                active &= Q(category__is_active=True)
            if key == "available" and self.model is ProductVariant:
                active &= Q(product__is_active=True, product__category__is_active=True)
            query = query.filter(active if raw == "true" else ~active)
        search = request.query_params.get("search", "")
        if len(search) > 80:
            raise ValidationError({"search": ["Use at most 80 characters."]})
        if search:
            query = query.filter(
                **{"sku__icontains" if self.model is ProductVariant else "name__icontains": search}
            )
        if "category_id" in request.query_params:
            from rest_framework.fields import UUIDField

            category_id = UUIDField().run_validation(request.query_params["category_id"])
            query = query.filter(category_id=category_id)
        if "sku" in request.query_params:
            sku = request.query_params["sku"].strip().upper()
            if len(sku) > 64:
                raise ValidationError({"sku": ["Use at most 64 characters."]})
            query = query.filter(variants__sku=sku)
        for key in ("size", "color"):
            if key in request.query_params:
                value = request.query_params[key].strip().lower()
                if len(value) > 40:
                    raise ValidationError({key: ["Use at most 40 characters."]})
                query = query.filter(**{key: value})
        return query.order_by("created_at", "id")

    def list(self, request):
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(self.filtered(request), request, view=self)
        return paginator.get_paginated_response(self.reader(page, many=True).data)

    def rendered(self, instance, status=200):
        return Response(self.reader(self.get_item(instance.pk)).data, status=status)


class CategoryList(CatalogView):
    model, reader, writer = Category, CategoryRead, CategoryWrite

    def get(self, request):
        return self.list(request)

    def post(self, request):
        return self.rendered(services.create_category(request.user, self.data(request)), 201)


class CategoryDetail(CategoryList):
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, pk):
        return Response(self.reader(self.get_item(pk)).data)

    def patch(self, request, pk):
        self.get_item(pk)
        return self.rendered(
            services.update_category(request.user, pk, self.data(request, partial=True))
        )


class ProductList(CatalogView):
    model, reader, writer = Product, ProductRead, ProductCreate
    filters = {"category_id", "sku"}

    def get(self, request):
        return self.list(request)

    def post(self, request):
        return self.rendered(services.create_product(request.user, self.data(request)), 201)


class ProductDetail(ProductList):
    http_method_names = ["get", "patch", "head", "options"]
    writer = ProductWrite

    def get(self, request, pk):
        return Response(self.reader(self.get_item(pk)).data)

    def patch(self, request, pk):
        self.get_item(pk)
        return self.rendered(
            services.update_product(request.user, pk, self.data(request, partial=True))
        )


class VariantList(CatalogView):
    model, reader, writer = ProductVariant, VariantRead, VariantWrite
    filters = {"size", "color"}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.product = services.scoped(Product, self.organization, kwargs["product_id"])

    def queryset(self):
        return super().queryset().filter(product=self.product)

    def get(self, request, product_id):
        return self.list(request)

    def post(self, request, product_id):
        return self.rendered(
            services.create_variant(request.user, product_id, self.data(request)), 201
        )


class VariantDetail(VariantList):
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, product_id, pk):
        return Response(self.reader(self.get_item(pk)).data)

    def patch(self, request, product_id, pk):
        self.get_item(pk)
        return self.rendered(
            services.update_variant(request.user, product_id, pk, self.data(request, partial=True))
        )
