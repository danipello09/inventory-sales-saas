from django.urls import path

from .views import (
    CategoryDetail,
    CategoryList,
    ProductDetail,
    ProductList,
    VariantDetail,
    VariantList,
)

urlpatterns = [
    path("categories/", CategoryList.as_view(), name="category-list"),
    path("categories/<uuid:pk>/", CategoryDetail.as_view(), name="category-detail"),
    path("products/", ProductList.as_view(), name="product-list"),
    path("products/<uuid:pk>/", ProductDetail.as_view(), name="product-detail"),
    path("products/<uuid:product_id>/variants/", VariantList.as_view(), name="variant-list"),
    path(
        "products/<uuid:product_id>/variants/<uuid:pk>/",
        VariantDetail.as_view(),
        name="variant-detail",
    ),
]
