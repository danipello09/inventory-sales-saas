from django.urls import path

from .api import AdjustmentView, InventoryList, MovementList

urlpatterns = [
    path("inventory/", InventoryList.as_view()),
    path("inventory/adjustments/", AdjustmentView.as_view()),
    path("inventory/movements/", MovementList.as_view()),
]
