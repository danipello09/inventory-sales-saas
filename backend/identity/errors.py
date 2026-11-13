from django.http import JsonResponse
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "The request conflicts with existing data."
    default_code = "conflict"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    details = response.data if isinstance(exc, ValidationError) else {}
    response.data = {
        "error": {
            "code": "validation_error"
            if isinstance(exc, ValidationError)
            else getattr(exc, "default_code", "error"),
            "message": "Invalid request."
            if details
            else str(getattr(exc, "detail", "Request failed.")),
            "details": details,
        }
    }
    response["Cache-Control"] = "no-store"
    return response


def csrf_failure(request, reason=""):
    return JsonResponse(
        {
            "error": {
                "code": "csrf_failed",
                "message": "CSRF verification failed.",
                "details": {},
            }
        },
        status=403,
        headers={"Cache-Control": "no-store"},
    )
