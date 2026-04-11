import pytest

from apps.policies.models import PolicyOutcome, PolicyRule


@pytest.mark.django_db
def test_analyst_cannot_delete_rule(analyst_api, policy_rules):
    rule = PolicyRule.objects.first()
    r = analyst_api.delete(f"/api/v1/rules/{rule.id}/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_api_client_cannot_list_audit_logs(api_client, jwt_for, api_client_user, policy_rules):
    token = jwt_for(api_client_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    r = api_client.get("/api/v1/audit-logs/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_admin_can_manage_rules(admin_api, policy_rules):
    r = admin_api.post(
        "/api/v1/rules/",
        {
            "name": "new",
            "priority": 5,
            "is_active": True,
            "condition": {"min_score": 99},
            "outcome": PolicyOutcome.DECLINED,
        },
        format="json",
    )
    assert r.status_code == 201
