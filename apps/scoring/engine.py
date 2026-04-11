from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings


@dataclass
class ScoreDTO:
    score: Decimal
    risk_band: str
    components: dict


class WeightedScoringEngine:
    """
    Modular scoring: weighted sum of numeric features, normalized to 0-100.
    Replace with ML model runner later by swapping the engine implementation.
    """

    def __init__(self, weights: dict[str, float] | None = None, version: str | None = None):
        self.weights = weights or getattr(
            settings,
            "SCORING_FEATURE_WEIGHTS",
            {"amount_risk": 0.35, "velocity": 0.25, "history": 0.25, "geo_risk": 0.15},
        )
        self.version = version or getattr(settings, "SCORING_ENGINE_VERSION", "weighted-v1")

    def score(self, features: dict) -> ScoreDTO:
        total_w = sum(self.weights.values()) or 1.0
        components: dict[str, float] = {}
        acc = 0.0
        for key, w in self.weights.items():
            raw = float(features.get(key, 0) or 0)
            raw = max(0.0, min(1.0, raw))
            contrib = (w / total_w) * raw * 100
            components[key] = round(contrib, 4)
            acc += contrib
        score = Decimal(str(round(min(100.0, max(0.0, acc)), 2)))
        risk_band = self._risk_band(float(score))
        return ScoreDTO(score=score, risk_band=risk_band, components=components)

    def _risk_band(self, score: float) -> str:
        thresholds = getattr(settings, "RISK_BAND_THRESHOLDS", {})
        for band, (lo, hi) in thresholds.items():
            if lo <= score < hi:
                return band
        return "medium"

