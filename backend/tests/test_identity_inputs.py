"""Request-boundary regressions for each implemented unsafe endpoint."""

import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Request-boundary-729!"
ENDPOINTS = [
    ("post", "auth/register/"),
    ("post", "auth/login/"),
    ("post", "auth/logout/"),
    ("patch", "organization/"),
]


@pytest.fixture
def boundary():
    user = User.objects.create_user("boundary@example.test", PASSWORD)
    organization = Organization.objects.create(name="Boundary Store")
    Membership.objects.create(user=user, organization=organization, role="ADMIN")
    client = APIClient(enforce_csrf_checks=True)
    return client, user, organization


def prepare(boundary, path):
    client, user, _ = boundary
    if path in ("auth/logout/", "organization/"):
        client.force_login(user)
    csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    payloads = {
        "auth/register/": {
            "email": "new@example.test",
            "password": PASSWORD,
            "organization_name": "New Store",
        },
        "auth/login/": {"email": user.email, "password": PASSWORD},
        "auth/logout/": {},
        "organization/": {"name": "Must not change"},
    }
    return client, csrf, payloads[path]


def assert_no_mutation(boundary, path):
    client, user, organization = boundary
    assert User.objects.count() == Organization.objects.count() == Membership.objects.count() == 1
    organization.refresh_from_db()
    assert organization.name == "Boundary Store"
    response = client.get("/api/v1/auth/me/")
    if path in ("auth/logout/", "organization/"):
        assert response.status_code == 200
        assert response.json()["id"] == str(user.pk)
    else:
        assert response.status_code == 401


@pytest.mark.parametrize("method,path", ENDPOINTS)
@pytest.mark.parametrize(
    "body", ['{"broken":', "[]", '[{"name":"bad"}]', '"text"', "null", "true", "42"]
)
def test_malformed_or_non_object_json_is_controlled_without_side_effects(
    boundary, method, path, body
):
    client, csrf, _ = prepare(boundary, path)
    response = getattr(client, method)(
        "/api/v1/" + path, body, content_type="application/json", HTTP_X_CSRFTOKEN=csrf
    )
    assert response.status_code == 400, response.data
    assert response.json()["error"]["code"] in ("parse_error", "validation_error")
    assert response["Cache-Control"] == "no-store"
    assert_no_mutation(boundary, path)


@pytest.mark.parametrize("method,path", ENDPOINTS)
@pytest.mark.parametrize("csrf_mode", ["missing", "mismatch", "hostile_origin"])
def test_each_unsafe_endpoint_enforces_csrf_without_side_effects(boundary, method, path, csrf_mode):
    client, csrf, payload = prepare(boundary, path)
    headers = {}
    if csrf_mode != "missing":
        headers["HTTP_X_CSRFTOKEN"] = "x" * 64 if csrf_mode == "mismatch" else csrf
    if csrf_mode == "hostile_origin":
        headers["HTTP_ORIGIN"] = "https://hostile.example.test"
    response = getattr(client, method)("/api/v1/" + path, payload, format="json", **headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert_no_mutation(boundary, path)


@pytest.mark.parametrize("method,path", ENDPOINTS)
@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded"])
def test_each_unsafe_endpoint_rejects_non_json_with_valid_csrf(
    boundary, method, path, content_type
):
    client, csrf, payload = prepare(boundary, path)
    response = getattr(client, method)(
        "/api/v1/" + path, json.dumps(payload), content_type=content_type, HTTP_X_CSRFTOKEN=csrf
    )
    assert response.status_code == 415, response.data
    assert_no_mutation(boundary, path)


def test_session_is_reused_by_a_new_client_and_replay_after_logout_is_denied(boundary):
    client, user, _ = boundary
    csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    session_id = client.cookies["sessionid"].value
    second = APIClient(enforce_csrf_checks=True)
    second.cookies["sessionid"] = session_id
    assert second.get("/api/v1/auth/me/").json()["id"] == str(user.pk)
    assert second.get("/api/v1/organization/").status_code == 200
    csrf = second.get("/api/v1/auth/csrf/").json()["csrfToken"]
    assert (
        second.post("/api/v1/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me/").status_code == 401
    assert client.get("/api/v1/organization/").status_code == 401
