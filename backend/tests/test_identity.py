import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.db.models.deletion import ProtectedError
from rest_framework.test import APIClient

from accounts.management.commands.migrate import check_legacy_schema
from identity.services import register_identity
from organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "River-forest-729!wide"
BASE = "/api/v1/"


@pytest.fixture
def client():
    return APIClient(enforce_csrf_checks=True)


def token(client):
    response = client.get(BASE + "auth/csrf/")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def post(client, path, data):
    return client.post(BASE + path, data, format="json", HTTP_X_CSRFTOKEN=token(client))


def patch(client, data):
    return client.patch(BASE + "organization/", data, format="json", HTTP_X_CSRFTOKEN=token(client))


def registration(**updates):
    return {
        "email": "owner@example.test",
        "password": PASSWORD,
        "organization_name": "Store One",
        **updates,
    }


@pytest.fixture
def tenants():
    # Real persisted records and sessions; authentication is exercised separately below.
    first = User.objects.create_user("first@example.test", PASSWORD)
    second = User.objects.create_user("second@example.test", PASSWORD)
    org1 = Organization.objects.create(name="First")
    org2 = Organization.objects.create(name="Second", currency="USD")
    member1 = Membership.objects.create(user=first, organization=org1, role="ADMIN")
    Membership.objects.create(user=second, organization=org2, role="ADMIN")
    return first, second, org1, org2, member1


def test_registration_creates_atomic_identity_and_real_session(client):
    response = post(client, "auth/register/", registration(email=" Owner@Example.Test "))
    assert response.status_code == 201, response.data
    data = response.json()
    assert uuid.UUID(data["id"])
    assert data["email"] == "owner@example.test"
    assert data["membership"]["role"] == "ADMIN"
    assert data["membership"]["organization"]["currency"] == "COP"
    user = User.objects.get()
    assert user.check_password(PASSWORD) and user.password != PASSWORD
    assert not user.is_staff and not user.is_superuser
    assert "password" not in str(data)
    assert client.get(BASE + "auth/me/").json() == data
    assert response["Cache-Control"] == "no-store"
    assert Organization.objects.count() == Membership.objects.count() == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"email": "invalid"},
        {"email": ""},
        {"password": "short"},
        {"password": "123456789012345"},
        {"organization_name": "   "},
        {"organization_name": "x" * 161},
        {"currency": "ZZZ"},
        {"role": "ADMIN"},
        {"is_superuser": True},
        {"organization_id": str(uuid.uuid4())},
        {"email": "a" * 250 + "@example.test"},
    ],
)
def test_invalid_registration_has_no_partial_rows(client, updates):
    response = post(client, "auth/register/", registration(**updates))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert User.objects.count() == Organization.objects.count() == Membership.objects.count() == 0


def test_registration_required_fields(client):
    response = post(client, "auth/register/", {})
    assert response.status_code == 400
    assert set(response.json()["error"]["details"]) == {"email", "password", "organization_name"}


def test_duplicate_case_variant_email_is_conflict(client):
    User.objects.create_user("owner@example.test", PASSWORD)
    response = post(client, "auth/register/", registration(email="OWNER@example.TEST"))
    assert response.status_code == 409
    assert User.objects.count() == 1
    assert Organization.objects.count() == Membership.objects.count() == 0


def test_registration_rollback_on_later_database_failure():
    # Bypass HTTP validation deliberately: the actual DB failure must roll back the user.
    with pytest.raises(IntegrityError):
        register_identity({**registration(), "currency": "ZZZ"})
    assert User.objects.count() == Organization.objects.count() == Membership.objects.count() == 0


def test_authenticated_registration_is_rejected(client, tenants):
    client.force_login(tenants[0])
    assert post(client, "auth/register/", registration()).status_code == 409
    assert User.objects.count() == 2


def test_login_rotates_session_and_csrf_and_logout_invalidates_session(client, tenants):
    session = client.session
    session["anonymous_marker"] = "before-login"
    session.save()
    old_key = session.session_key
    old_csrf = token(client)
    old_cookie = client.cookies["csrftoken"].value
    response = client.post(
        BASE + "auth/login/",
        {"email": "FIRST@EXAMPLE.TEST", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=old_csrf,
    )
    assert response.status_code == 200, response.data
    assert client.session.session_key != old_key
    assert client.cookies["csrftoken"].value != old_cookie
    assert client.get(BASE + "auth/me/").json()["id"] == str(tenants[0].pk)
    authenticated_key = client.session.session_key
    assert post(client, "auth/logout/", {}).status_code == 204
    assert client.get(BASE + "auth/me/").status_code == 401
    other = APIClient()
    other.cookies["sessionid"] = authenticated_key
    assert other.get(BASE + "auth/me/").status_code == 401


@pytest.mark.parametrize(
    "email,password,inactive",
    [
        ("missing@example.test", PASSWORD, False),
        ("first@example.test", "wrong", False),
        ("first@example.test", PASSWORD, True),
    ],
)
def test_invalid_credentials_and_inactive_users_are_indistinguishable(
    client,
    tenants,
    email,
    password,
    inactive,
):
    if inactive:
        tenants[0].is_active = False
        tenants[0].save(update_fields=["is_active"])
    response = post(client, "auth/login/", {"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_inactive_existing_session_loses_access(client, tenants):
    client.force_login(tenants[0])
    User.objects.filter(pk=tenants[0].pk).update(is_active=False)
    assert client.get(BASE + "auth/me/").status_code == 401
    assert client.get(BASE + "organization/").status_code == 401


@pytest.mark.parametrize("path", ["auth/me/", "organization/"])
def test_unauthenticated_read_is_401(client, path):
    response = client.get(BASE + path)
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"


@pytest.mark.parametrize("path", ["auth/register/", "auth/login/", "auth/logout/"])
def test_unsafe_identity_requires_csrf_even_anonymous(client, path):
    response = client.post(BASE + path, registration(), format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_csrf_mismatch_and_hostile_origin_are_rejected(client, tenants):
    csrf = token(client)
    response = client.post(BASE + "auth/login/", {}, format="json", HTTP_X_CSRFTOKEN="x" * 64)
    assert response.status_code == 403
    response = client.post(
        BASE + "auth/login/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
        HTTP_ORIGIN="https://attacker.example.test",
    )
    assert response.status_code == 403
    client.force_login(tenants[0])
    assert (
        client.patch(BASE + "organization/", {"name": "Bypass"}, format="json").status_code == 403
    )
    tenants[2].refresh_from_db()
    assert tenants[2].name == "First"


def test_local_and_production_cookie_flags(client, settings):
    settings.SESSION_COOKIE_SECURE = settings.CSRF_COOKIE_SECURE = True
    response = post(client, "auth/register/", registration())
    assert response.status_code == 201
    for key in ("sessionid", "csrftoken"):
        assert response.cookies[key]["httponly"]
        assert response.cookies[key]["secure"]
        assert response.cookies[key]["samesite"] == "Lax"
    settings.SESSION_COOKIE_SECURE = settings.CSRF_COOKIE_SECURE = False
    response = client.get(BASE + "auth/csrf/")
    assert not response.cookies["csrftoken"]["secure"]
    assert response.cookies["csrftoken"]["httponly"]


def test_csrf_rotation_rejects_pre_login_token_and_accepts_same_origin(client, tenants):
    old_token = token(client)
    response = client.post(
        BASE + "auth/login/",
        {"email": tenants[0].email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=old_token,
        HTTP_ORIGIN="http://testserver",
    )
    assert response.status_code == 200
    response = client.patch(
        BASE + "organization/",
        {"name": "Stale"},
        format="json",
        HTTP_X_CSRFTOKEN=old_token,
    )
    assert response.status_code == 403
    assert patch(client, {"name": "Fresh"}).status_code == 200


def test_writes_are_json_only_and_logout_fields_are_strict(client, tenants):
    response = client.post(
        BASE + "auth/login/",
        {"email": tenants[0].email, "password": PASSWORD},
        format="multipart",
        HTTP_X_CSRFTOKEN=token(client),
    )
    assert response.status_code == 415, response.data
    client.force_login(tenants[0])
    assert post(client, "auth/logout/", {"organization_id": "other"}).status_code == 400
    assert client.get(BASE + "auth/me/").status_code == 200


def test_admin_reads_and_updates_only_own_organization(client, tenants):
    first, second, org1, org2, _ = tenants
    client.force_login(first)
    assert client.get(BASE + "organization/").json()["id"] == str(org1.pk)
    assert patch(client, {"name": " Renamed "}).status_code == 200
    org1.refresh_from_db()
    org2.refresh_from_db()
    assert org1.name == "Renamed" and org2.name == "Second"
    client.force_login(second)
    assert client.get(BASE + "organization/").json()["id"] == str(org2.pk)
    assert patch(client, {"name": "Second Renamed"}).status_code == 200
    org1.refresh_from_db()
    assert org1.name == "Renamed"
    assert client.get(BASE + f"organization/{org1.pk}/").status_code == 404


def test_staff_read_allowed_update_denied(client, tenants):
    member = tenants[4]
    member.role = "STAFF"
    member.save(update_fields=["role"])
    client.force_login(tenants[0])
    assert client.get(BASE + "organization/").status_code == 200
    assert patch(client, {"name": "Forbidden"}).status_code == 403
    tenants[2].refresh_from_db()
    assert tenants[2].name == "First"


@pytest.mark.parametrize(
    "injected",
    [
        {"organization_id": "other"},
        {"id": "other"},
        {"status": "ACTIVE"},
        {"currency": "USD"},
        {"role": "ADMIN"},
        {"is_superuser": True},
    ],
)
def test_admin_cannot_mass_assign_tenant_or_privilege_fields(client, tenants, injected):
    client.force_login(tenants[0])
    response = patch(client, {"name": "Must rollback", **injected})
    assert response.status_code == 400
    tenants[2].refresh_from_db()
    assert tenants[2].name == "First"


@pytest.mark.parametrize("data", [{}, {"name": " "}, {"name": "a" * 161}])
def test_invalid_organization_update(client, tenants, data):
    client.force_login(tenants[0])
    assert patch(client, data).status_code == 400


@pytest.mark.parametrize(
    "mode", ["suspended", "inactive_membership", "missing_membership", "platform"]
)
def test_tenant_denials_keep_me_and_logout_available(client, tenants, mode):
    first, _, org1, _, member = tenants
    if mode == "suspended":
        org1.status = "SUSPENDED"
        org1.save(update_fields=["status"])
    elif mode == "inactive_membership":
        member.is_active = False
        member.save(update_fields=["is_active"])
    elif mode == "missing_membership":
        member.delete()
    else:
        first.is_superuser = True
        first.save(update_fields=["is_superuser"])
    client.force_login(first)
    assert client.get(BASE + "auth/me/").status_code == 200
    assert client.get(BASE + "organization/").status_code == 403
    assert patch(client, {"name": "Forbidden"}).status_code == 403
    assert post(client, "auth/logout/", {}).status_code == 204


def test_suspended_organization_can_login_but_not_operate(client, tenants):
    org = tenants[2]
    org.status = "SUSPENDED"
    org.save(update_fields=["status"])
    assert (
        post(client, "auth/login/", {"email": tenants[0].email, "password": PASSWORD}).status_code
        == 200
    )
    assert (
        client.get(BASE + "auth/me/").json()["membership"]["organization"]["status"] == "SUSPENDED"
    )
    assert client.get(BASE + "organization/").status_code == 403


def test_database_constraints_and_protected_relationships(tenants):
    first, _, org1, org2, _ = tenants
    attempts = [
        lambda: Membership.objects.create(user=first, organization=org2, role="ADMIN"),
        lambda: Membership.objects.filter(user=first).update(role="ROOT"),
        lambda: Membership.objects.filter(user=first).update(organization_id=uuid.uuid4()),
        lambda: Organization.objects.filter(pk=org1.pk).update(status="DELETED"),
        lambda: Organization.objects.filter(pk=org1.pk).update(currency="ZZZ"),
        lambda: Organization.objects.filter(pk=org1.pk).update(name="   "),
        lambda: User.objects.create(email=first.email, password="not-a-real-hash"),
        lambda: User.objects.create(email=first.email.upper(), password="not-a-real-hash"),
        lambda: User.objects.create(email="", password="not-a-real-hash"),
    ]
    for attempt in attempts:
        with pytest.raises(IntegrityError), transaction.atomic():
            attempt()
            connection.check_constraints()  # PostgreSQL FKs are deferred by Django.
    with pytest.raises(ProtectedError):
        org1.delete()
    with pytest.raises(ProtectedError):
        first.delete()


def test_user_manager_and_superuser_contract():
    user = User.objects.create_superuser(" Admin@Example.TEST ", PASSWORD)
    assert user.email == "admin@example.test" and user.is_superuser and user.is_staff
    with pytest.raises(ValueError):
        User.objects.create_superuser("bad@example.test", PASSWORD, is_staff=False)


def test_malformed_json_and_methods(client):
    response = client.post(
        BASE + "auth/login/",
        "{broken",
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token(client),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "parse_error"
    assert client.get(BASE + "auth/login/").status_code == 405


def test_new_schema_and_legacy_history_guard():
    check_legacy_schema(connection)
    applied = MigrationRecorder(connection).applied_migrations()
    assert ("accounts", "0001_initial") in applied
    assert ("organizations", "0001_initial") in applied
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM django_migrations WHERE app = 'accounts'")
    with pytest.raises(CommandError, match="Legacy auth.User database"):
        call_command("migrate", interactive=False, verbosity=0)
    # pytest's enclosing transaction restores the history after this denial test.
