import pytest
from rest_framework.test import APIClient

from apps.authentication.models import User, UserRole


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@example.com",
        password="pass12345",
        role=UserRole.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst@example.com",
        password="pass12345",
        role=UserRole.ANALYST,
    )


@pytest.fixture
def api_client_user(db):
    return User.objects.create_user(
        email="client@example.com",
        password="pass12345",
        role=UserRole.API_CLIENT,
    )


@pytest.fixture
def admin_api(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def analyst_api(api_client, analyst_user):
    api_client.force_authenticate(user=analyst_user)
    return api_client


@pytest.fixture
def jwt_for(api_client):
    def _get(user):
        r = api_client.post(
            "/api/v1/auth/login",
            {"email": user.email, "password": "pass12345"},
            format="json",
        )
        assert r.status_code == 200, r.content
        return r.json()["access"]

    return _get


@pytest.fixture
def policy_rules(db):
    from apps.policies.models import PolicyOutcome, PolicyRule

    PolicyRule.objects.all().delete()
    PolicyRule.objects.create(
        name="t-decline-high",
        priority=5,
        is_active=True,
        condition={"risk_band": "high"},
        outcome=PolicyOutcome.DECLINED,
    )
    PolicyRule.objects.create(
        name="t-approve-low",
        priority=50,
        is_active=True,
        condition={"risk_band": "low", "max_score": 100},
        outcome=PolicyOutcome.APPROVED,
    )
    PolicyRule.objects.create(
        name="t-catch",
        priority=999,
        is_active=True,
        condition={},
        outcome=PolicyOutcome.MANUAL_REVIEW,
    )
