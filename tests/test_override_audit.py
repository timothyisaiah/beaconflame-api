import pytest

from apps.audits.constants import EventType
from apps.audits.models import AuditLog
from apps.decisions.models import DecisionType


@pytest.mark.django_db
def test_override_flow(api_client, jwt_for, analyst_user, policy_rules):
    token = jwt_for(analyst_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    r = api_client.post(
        "/api/v1/applications/",
        {"payload": {"amount": 1000, "velocity_score": 0.1, "history_score": 0.2, "geo_risk": 0.1}},
        format="json",
    )
    assert r.status_code == 201
    app_id = r.json()["id"]
    r2 = api_client.post(
        f"/api/v1/applications/{app_id}/override/",
        {"decision_type": DecisionType.APPROVED, "reason": "Verified manually"},
        format="json",
    )
    assert r2.status_code == 200
    assert AuditLog.objects.filter(event_type=EventType.DECISION_OVERRIDDEN).exists()
