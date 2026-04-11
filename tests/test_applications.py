import pytest

from apps.applications.models import Application
from apps.applications.tasks import enqueue_pipeline
from apps.audits.constants import EventType
from apps.audits.models import AuditLog
from apps.decisions.models import Decision


@pytest.mark.django_db
def test_submit_application_pipeline_eager(api_client, jwt_for, analyst_user, policy_rules):
    token = jwt_for(analyst_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    r = api_client.post(
        "/api/v1/applications/",
        {"payload": {"amount": 1000, "velocity_score": 0.1, "history_score": 0.2, "geo_risk": 0.1}},
        format="json",
    )
    assert r.status_code == 201
    app_id = r.json()["id"]
    app = Application.objects.get(pk=app_id)
    assert app.status in ("approved", "declined", "manual_review")
    assert Decision.objects.filter(application=app, is_current=True).exists()
    assert AuditLog.objects.filter(event_type=EventType.APPLICATION_SUBMITTED).exists()


@pytest.mark.django_db
def test_idempotent_submission(api_client, jwt_for, analyst_user, policy_rules):
    token = jwt_for(analyst_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    body = {"payload": {"amount": 500, "velocity_score": 0.1, "history_score": 0.5, "geo_risk": 0.2}}
    r1 = api_client.post("/api/v1/applications/", body, format="json", HTTP_IDEMPOTENCY_KEY="idem-1")
    r2 = api_client.post("/api/v1/applications/", body, format="json", HTTP_IDEMPOTENCY_KEY="idem-1")
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert Application.objects.filter(idempotency_key="idem-1").count() == 1


@pytest.mark.django_db
def test_get_decision(api_client, jwt_for, analyst_user, policy_rules):
    token = jwt_for(analyst_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    r = api_client.post(
        "/api/v1/applications/",
        {"payload": {"amount": 1000, "velocity_score": 0.1, "history_score": 0.2, "geo_risk": 0.1}},
        format="json",
    )
    app_id = r.json()["id"]
    d = api_client.get(f"/api/v1/applications/{app_id}/decision/")
    assert d.status_code == 200
    assert "decision_type" in d.json()
