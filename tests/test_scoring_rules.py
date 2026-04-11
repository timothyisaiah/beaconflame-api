import pytest

from apps.policies.engine import RuleEngine
from apps.policies.models import PolicyOutcome, PolicyRule


@pytest.mark.django_db
def test_weighted_scoring_engine():
    from apps.scoring.engine import WeightedScoringEngine

    eng = WeightedScoringEngine(weights={"amount_risk": 1.0}, version="test")
    dto = eng.score({"amount_risk": 0.5})
    assert dto.score == pytest.approx(50.0, rel=1e-2)
    assert dto.risk_band in ("low", "medium", "high")


@pytest.mark.django_db
def test_rule_engine_first_match():
    r1 = PolicyRule(name="a", priority=1, is_active=True, condition={"min_score": 90}, outcome=PolicyOutcome.DECLINED)
    r1.save()
    r2 = PolicyRule(name="b", priority=2, is_active=True, condition={}, outcome=PolicyOutcome.APPROVED)
    r2.save()
    res = RuleEngine().evaluate([r1, r2], {"score": 95, "risk_band": "medium", "features": {}})
    assert res.matched_rule_id == str(r1.id)
    assert res.outcome == PolicyOutcome.DECLINED
