"""Derive scoring features from raw application payload (placeholder enrichment output)."""


def compute_feature_dict(raw_payload: dict) -> dict:
    amount = float(raw_payload.get("amount", 0) or 0)
    amount_risk = min(1.0, amount / 50_000.0)
    velocity = float(raw_payload.get("velocity_score", 0) or 0)
    velocity = max(0.0, min(1.0, velocity))
    history = float(raw_payload.get("history_score", 0.5) or 0.5)
    history = max(0.0, min(1.0, history))
    geo_risk = float(raw_payload.get("geo_risk", 0.2) or 0.2)
    geo_risk = max(0.0, min(1.0, geo_risk))
    return {
        "amount_risk": amount_risk,
        "velocity": velocity,
        "history": history,
        "geo_risk": geo_risk,
    }
