"""Health and the first identity/organization backend slice."""
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [path("health/", health, name="health"), path("api/v1/", include("identity.urls"))]
