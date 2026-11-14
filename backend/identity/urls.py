from django.urls import path

from .views import CsrfView, LoginView, LogoutView, MeView, OrganizationView, RegisterView

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="csrf"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("organization/", OrganizationView.as_view(), name="organization"),
]
