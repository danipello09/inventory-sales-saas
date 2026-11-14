from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied

from accounts.models import User
from organizations.models import Membership, Organization

from .errors import Conflict


def register_identity(data):
    try:
        with transaction.atomic():
            user = User.objects.create_user(email=data["email"], password=data["password"])
            organization = Organization.objects.create(
                name=data["organization_name"],
                currency=data["currency"],
            )
            Membership.objects.create(
                user=user, organization=organization, role=Membership.Role.ADMIN
            )
    except IntegrityError as error:
        if User.objects.filter(email=data["email"]).exists():
            raise Conflict("Registration could not be completed for this email.") from error
        raise
    return user


def organization_for_user(user, *, admin=False, lock=False):
    if not user.is_active or user.is_superuser:
        raise PermissionDenied("This account cannot access tenant operations.")
    memberships = Membership.objects.filter(user=user, is_active=True)
    if lock:
        memberships = memberships.select_for_update()
    membership = memberships.first()
    if membership is None or (admin and membership.role != Membership.Role.ADMIN):
        raise PermissionDenied("An active membership with the required role is needed.")
    organizations = Organization.objects
    if lock:
        organizations = organizations.select_for_update()
    organization = organizations.get(pk=membership.organization_id)
    if organization.status != Organization.Status.ACTIVE:
        raise PermissionDenied("The organization is suspended.")
    return organization


@transaction.atomic
def update_organization(user, data):
    organization = organization_for_user(user, admin=True, lock=True)
    organization.name = data["name"]
    organization.save(update_fields=["name", "updated_at"])
    return organization
