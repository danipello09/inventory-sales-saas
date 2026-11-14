from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User
from organizations.models import Organization


class StrictSerializer(serializers.Serializer):
    """Reject unknown fields rather than silently ignore privilege/tenant injection."""

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: ["Unknown field."] for key in unknown})
        return super().to_internal_value(data)


class CredentialsSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class RegistrationSerializer(CredentialsSerializer):
    organization_name = serializers.CharField(max_length=160)
    currency = serializers.ChoiceField(choices=Organization.Currency, default="COP")

    def validate(self, attrs):
        try:
            validate_password(attrs["password"], User(email=attrs["email"]))
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs


class OrganizationUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=160)


class EmptySerializer(StrictSerializer):
    pass


def organization_data(organization):
    return {
        "id": str(organization.pk),
        "name": organization.name,
        "currency": organization.currency,
        "status": organization.status,
    }


def identity_data(user):
    membership = user.membership if hasattr(user, "membership") else None
    return {
        "id": str(user.pk),
        "email": user.email,
        "membership": None
        if membership is None
        else {
            "role": membership.role,
            "is_active": membership.is_active,
            "organization": organization_data(membership.organization),
        },
    }
