from __future__ import annotations

from typing import TYPE_CHECKING

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

if TYPE_CHECKING:
    from apps.authentication.models import User


def verify_google_id_token(raw_token: str, audiences: list[str]) -> dict:
    """
    Validate a Google Sign-In ID token and return decoded claims.

    `audiences` must list every OAuth 2.0 client ID you accept (e.g. web app).
    """
    if not audiences:
        raise ValueError("Google sign-in is not configured.")
    request = google_requests.Request()
    audience = audiences[0] if len(audiences) == 1 else audiences
    try:
        return id_token.verify_oauth2_token(raw_token, request, audience=audience)
    except GoogleAuthError as exc:
        raise ValueError("Invalid Google token.") from exc


def user_for_google_oauth_email(email: str) -> User:
    """Return existing user or create an analyst with no usable password."""
    from apps.authentication.models import User, UserRole

    normalized = User.objects.normalize_email(email)
    try:
        return User.objects.get(email=normalized)
    except User.DoesNotExist:
        return User.objects.create_user(email=normalized, password=None, role=UserRole.ANALYST)
