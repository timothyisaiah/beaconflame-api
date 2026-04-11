from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.urls import reverse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def _wants_browser_login_redirect(django_request):
    if not django_request.path.startswith("/api/"):
        return False
    if django_request.GET.get("format") == "html":
        return True
    return django_request.headers.get("Sec-Fetch-Mode") == "navigate"


def custom_exception_handler(exc, context):
    request = context.get("request")
    if request is not None and isinstance(exc, exceptions.NotAuthenticated):
        django_request = getattr(request, "_request", request)
        if _wants_browser_login_redirect(django_request):
            next_path = django_request.get_full_path()
            if not next_path.startswith("/") or next_path.startswith("//"):
                next_path = "/"
            login_url = f"{reverse('browser-login')}?{urlencode({'next': next_path})}"
            return HttpResponseRedirect(login_url)

    response = drf_exception_handler(exc, context)
    if response is not None:
        code = getattr(exc, "default_code", "error")
        message = str(exc.detail) if hasattr(exc, "detail") else str(exc)
        details = exc.detail if hasattr(exc, "detail") and isinstance(exc.detail, (dict, list)) else None
        if isinstance(exc.detail, dict) and len(exc.detail) == 1:
            first = next(iter(exc.detail.values()))
            if isinstance(first, list) and len(first) == 1:
                message = str(first[0])
        response.data = {
            "error": {
                "code": str(code),
                "message": message if isinstance(message, str) else "Validation error",
                "details": details if isinstance(details, (dict, list)) else None,
            }
        }
        return response

    return Response(
        {
            "error": {
                "code": "server_error",
                "message": "An unexpected error occurred.",
                "details": None,
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
