from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
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
