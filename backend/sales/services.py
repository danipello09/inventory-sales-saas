from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from identity.errors import Conflict
from identity.services import organization_for_user
from inventory.services import change_stock, locked_variant

from .models import Sale, SaleItem


@transaction.atomic
def create_sale(user, data):
    organization = organization_for_user(user, lock=True)
    # UUID order is consistent across sales, adjustments and cancellations.
    items = sorted(data["items"], key=lambda item: str(item["variant_id"]))
    variants = [
        (locked_variant(organization, item["variant_id"]), item["quantity"]) for item in items
    ]
    for variant, _ in variants:
        if not variant.is_available:
            raise Conflict("The variant, product or category is inactive.")
    total = sum((variant.price * quantity for variant, quantity in variants), Decimal("0.00"))
    if total > Decimal("99999999999999"):
        raise Conflict("Sale total limit exceeded.")
    sale = Sale.objects.create(
        organization=organization,
        creator=user,
        currency=organization.currency,
        total=total,
    )
    for variant, quantity in variants:
        SaleItem.objects.create(
            organization=organization,
            sale=sale,
            variant=variant,
            sku=variant.sku,
            quantity=quantity,
            unit_price=variant.price,
            subtotal=variant.price * quantity,
        )
        change_stock(organization, variant, -quantity, actor=user, reason="Sale", sale=sale)
    return sale


@transaction.atomic
def cancel_sale(user, pk, reason):
    organization = organization_for_user(user, admin=True, lock=True)
    sale = get_object_or_404(
        Sale.objects.select_for_update().filter(organization=organization),
        pk=pk,
    )
    if sale.status == "CANCELLED":
        return sale
    for item in sale.items.order_by("variant_id"):
        variant = locked_variant(organization, item.variant_id)
        change_stock(
            organization,
            variant,
            item.quantity,
            actor=user,
            reason="Cancellation: " + reason[:140],
            sale=sale,
        )
    sale.status = "CANCELLED"
    sale.cancelled_at = timezone.now()
    sale.cancelled_by = user
    sale.cancellation_reason = reason
    sale.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason"])
    return sale
