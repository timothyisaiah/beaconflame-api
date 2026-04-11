import logging
import uuid

logger = logging.getLogger(__name__)

CORRELATION_HEADER = "HTTP_X_REQUEST_ID"


class CorrelationIdMiddleware:
    """Attach X-Request-Id to request and response; log structured context."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.META.get(CORRELATION_HEADER) or str(uuid.uuid4())
        request.correlation_id = cid
        response = self.get_response(request)
        response["X-Request-Id"] = cid
        return response
