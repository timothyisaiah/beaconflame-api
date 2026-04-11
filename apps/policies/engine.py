"""
Policy rule evaluation: deterministic first-match wins.

Rules are ordered by (priority ascending, id ascending). The first rule whose
condition matches the evaluation context determines the outcome.
An empty condition dict matches immediately (useful as a catch-all with low priority).
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.policies.models import PolicyOutcome, PolicyRule


@dataclass
class RuleEvaluationResult:
    matched_rule_id: str | None
    outcome: str
    matched: bool
    evaluated_rules: list[dict]


class RuleEngine:
    def evaluate(self, rules: list[PolicyRule], context: dict) -> RuleEvaluationResult:
        evaluated: list[dict] = []
        for rule in rules:
            if not rule.is_active:
                continue
            matched = self._matches(rule.condition, context)
            evaluated.append(
                {
                    "rule_id": str(rule.id),
                    "name": rule.name,
                    "priority": rule.priority,
                    "matched": matched,
                    "outcome": rule.outcome,
                }
            )
            if matched:
                return RuleEvaluationResult(
                    matched_rule_id=str(rule.id),
                    outcome=rule.outcome,
                    matched=True,
                    evaluated_rules=evaluated,
                )
        return RuleEvaluationResult(
            matched_rule_id=None,
            outcome=PolicyOutcome.MANUAL_REVIEW,
            matched=False,
            evaluated_rules=evaluated,
        )

    def _matches(self, condition: dict, context: dict) -> bool:
        if not condition:
            return True
        if "min_score" in condition:
            if float(context.get("score", 0)) < float(condition["min_score"]):
                return False
        if "max_score" in condition:
            if float(context.get("score", 0)) > float(condition["max_score"]):
                return False
        if "risk_band" in condition:
            if context.get("risk_band") != condition["risk_band"]:
                return False
        if "feature_equals" in condition and "feature_path" in condition:
            path = condition["feature_path"]
            expected = condition["feature_equals"]
            actual = self._resolve_path(context.get("features") or {}, path)
            if actual != expected:
                return False
        if "feature_min" in condition and "feature_path" in condition:
            path = condition["feature_path"]
            minimum = float(condition["feature_min"])
            actual = self._resolve_path(context.get("features") or {}, path)
            try:
                if float(actual) < minimum:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _resolve_path(self, data: dict, path: str):
        cur = data
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur


def decimal_to_float(val):
    if isinstance(val, Decimal):
        return float(val)
    return float(val or 0)
