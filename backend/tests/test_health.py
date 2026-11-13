from django.test import Client
from django.urls import reverse


def test_health_endpoint():
    response = Client().get(reverse("health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
