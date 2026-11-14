from django.urls import path

from .api import CancelView, SaleDetail, SaleList

urlpatterns = [
    path("sales/", SaleList.as_view()),
    path("sales/<uuid:pk>/", SaleDetail.as_view()),
    path("sales/<uuid:pk>/cancel/", CancelView.as_view()),
]
