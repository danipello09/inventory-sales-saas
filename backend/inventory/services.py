from django.db import transaction
from django.shortcuts import get_object_or_404

from catalog.models import ProductVariant
from identity.errors import Conflict
from identity.services import organization_for_user

from .models import InventoryBalance, StockMovement


def locked_variant(organization, pk):
    return get_object_or_404(
        ProductVariant.objects.select_for_update().filter(organization=organization),
        pk=pk,
    )


def locked_balance(organization, variant):
    # Caller holds the variant row lock: even first-row creation is serialized.
    balance, _ = InventoryBalance.objects.get_or_create(
        organization=organization,
        variant=variant,
    )
    return InventoryBalance.objects.select_for_update().get(pk=balance.pk)


def change_stock(organization, variant, delta, *, actor, reason, sale=None):
    balance = locked_balance(organization, variant)
    quantity = balance.quantity + delta
    if not 0 <= quantity <= 2147483647:
        raise Conflict("Insufficient stock or inventory limit exceeded.")
    balance.quantity = quantity
    balance.save(update_fields=["quantity"])
    StockMovement.objects.create(
        organization=organization,
        variant=variant,
        delta=delta,
        actor=actor,
        reason=reason,
        sale=sale,
    )
    return balance


@transaction.atomic
def adjust_stock(user, data):
    organization = organization_for_user(user, admin=True, lock=True)
    variant = locked_variant(organization, data["variant_id"])
    return change_stock(
        organization,
        variant,
        data["delta"],
        actor=user,
        reason=data["reason"],
    )
