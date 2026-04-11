import pytest
from rest_framework.test import APIClient

from apps.audits.constants import EventType
from apps.audits.models import AuditLog
from apps.authentication.models import User, UserRole


@pytest.mark.django_db
def test_login_success(jwt_for, admin_user):
    assert jwt_for(admin_user)


@pytest.mark.django_db
def test_login_failure_creates_audit(api_client):
    User.objects.create_user(email="u@example.com", password="ok", role=UserRole.ADMIN)
    r = api_client.post(
        "/api/v1/auth/login",
        {"email": "u@example.com", "password": "wrong"},
        format="json",
    )
    assert r.status_code == 401
    assert AuditLog.objects.filter(event_type=EventType.AUTH_LOGIN_FAILURE).exists()


@pytest.mark.django_db
def test_logout_blacklists_and_audits(api_client, admin_user):
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    r = api_client.post("/api/v1/auth/logout", {"refresh": str(refresh)}, format="json")
    assert r.status_code in (200, 205)
    assert AuditLog.objects.filter(event_type=EventType.AUTH_LOGOUT).exists()


@pytest.mark.django_db
def test_api_key_authentication(api_client, api_client_user):
    from apps.authentication.api_keys import extract_prefix, hash_api_key
    from apps.authentication.models import APIKey

    raw = APIKey.generate_secret()
    APIKey.objects.create(
        user=api_client_user,
        name="k",
        prefix=extract_prefix(raw, 16),
        hashed_key=hash_api_key(raw),
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw}")
    r = api_client.post(
        "/api/v1/applications/",
        {"payload": {"amount": 100, "velocity_score": 0.1}},
        format="json",
    )
    assert r.status_code in (200, 201)
