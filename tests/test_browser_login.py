import json
from unittest.mock import patch

import pytest
from django.test import Client, override_settings


@pytest.mark.django_db
def test_api_navigate_unauthenticated_redirects_to_login():
    c = Client()
    r = c.get("/api/v1/applications/", HTTP_SEC_FETCH_MODE="navigate")
    assert r.status_code == 302
    assert r["Location"].startswith("/login/?")
    assert "next=" in r["Location"]


@pytest.mark.django_db
def test_api_without_navigate_returns_401_json():
    c = Client()
    r = c.get("/api/v1/applications/")
    assert r.status_code == 401
    data = r.json()
    assert "error" in data


@pytest.mark.django_db
def test_login_page_renders():
    c = Client()
    r = c.get("/login/")
    assert r.status_code == 200
    assert b"Sign in" in r.content


@pytest.mark.django_db
def test_coop_header_allows_google_sign_in_popups(client):
    """Django's default COOP is same-origin; we relax it so GIS / OAuth popups can postMessage."""
    r = client.get("/login/")
    assert r.status_code == 200
    assert r.headers.get("Cross-Origin-Opener-Policy") == "same-origin-allow-popups"


@pytest.mark.django_db
def test_browser_password_login_session_can_list_applications(client, admin_user):
    client.get("/login/")
    r = client.post(
        "/login/",
        {"email": admin_user.email, "password": "pass12345", "next": "/api/v1/applications/"},
    )
    assert r.status_code == 302
    r2 = client.get("/api/v1/applications/")
    assert r2.status_code == 200


@pytest.mark.django_db
@override_settings(GOOGLE_OAUTH_CLIENT_ID=["test.apps.googleusercontent.com"])
@patch("apps.authentication.browser_views.verify_google_id_token")
def test_browser_google_login_sets_session(mock_verify, client):
    mock_verify.return_value = {
        "email": "browser-google@example.com",
        "email_verified": True,
        "aud": "test.apps.googleusercontent.com",
    }
    client.get("/login/")
    r = client.post(
        "/login/google/",
        data=json.dumps({"credential": "fake", "next": "/"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["redirect"] == "/"
