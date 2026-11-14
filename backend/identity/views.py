from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, UnsupportedMediaType
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import Conflict
from .serializers import (
    CredentialsSerializer,
    EmptySerializer,
    OrganizationUpdateSerializer,
    RegistrationSerializer,
    identity_data,
    organization_data,
)
from .services import organization_for_user, register_identity, update_organization


class SessionChallengeAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        return "Session"


@method_decorator(csrf_protect, name="dispatch")
class IdentityAPIView(APIView):
    authentication_classes = [SessionChallengeAuthentication]
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            media_type = request.content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                raise UnsupportedMediaType(media_type)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class CsrfView(IdentityAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request._request)})


class RegisterView(IdentityAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            raise Conflict("Log out before registering another identity.")
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_identity(serializer.validated_data)
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(identity_data(user), status=201)


class LoginView(IdentityAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = authenticate(request._request, email=data["email"], password=data["password"])
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")
        login(request._request, user)
        return Response(identity_data(user))

    def get_authenticate_header(self, request):
        return "Session"


class LogoutView(IdentityAPIView):
    def post(self, request):
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logout(request._request)
        return Response(status=204)


class MeView(IdentityAPIView):
    def get(self, request):
        return Response(identity_data(request.user))


class OrganizationView(IdentityAPIView):
    def get(self, request):
        return Response(organization_data(organization_for_user(request.user)))

    def patch(self, request):
        serializer = OrganizationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            organization_data(update_organization(request.user, serializer.validated_data))
        )
