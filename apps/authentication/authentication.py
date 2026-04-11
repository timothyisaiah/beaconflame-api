from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.authentication.api_keys import extract_prefix, verify_api_key
from apps.authentication.models import APIKey


def _api_key_from_header(request) -> str | None:
    authz = request.META.get("HTTP_AUTHORIZATION", "")
    if authz.startswith("Api-Key "):
        return authz[8:].strip()
    x = request.META.get("HTTP_X_API_KEY")
    if x:
        return x.strip()
    return None


class BearerOrApiKeyAuthentication(authentication.BaseAuthentication):
    """
    Supports Authorization: Bearer <jwt> and Api-Key / X-Api-Key for external clients.
    """

    www_authenticate_realm = "api"

    def authenticate(self, request):
        jwt_auth = JWTAuthentication()
        header = jwt_auth.get_header(request)
        if header is not None:
            raw_token = jwt_auth.get_raw_token(header)
            if raw_token is not None:
                try:
                    validated = jwt_auth.get_validated_token(raw_token)
                    return jwt_auth.get_user(validated), validated
                except (InvalidToken, TokenError) as exc:
                    raise AuthenticationFailed("Invalid token.") from exc
                except AuthenticationFailed:
                    raise

        raw_key = _api_key_from_header(request)
        if not raw_key:
            return None

        prefix = extract_prefix(raw_key, 16)
        candidates = list(APIKey.objects.select_related("user").filter(prefix=prefix, revoked_at__isnull=True))
        for key in candidates:
            if verify_api_key(raw_key, key.hashed_key):
                key.last_used_at = timezone.now()
                key.save(update_fields=["last_used_at"])
                request.api_key = key
                return key.user, key
        raise AuthenticationFailed("Invalid API key.")

    def authenticate_header(self, request):
        return 'Bearer realm="%s"' % self.www_authenticate_realm
