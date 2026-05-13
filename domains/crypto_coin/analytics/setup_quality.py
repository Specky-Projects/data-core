"""Setup quality scoring for analysis and shadow/live diagnostics."""

from __future__ import annotations


def compute_setup_score(ind, mtf_bias: str | None = None, confidence_adjustment: int = 0) -> dict:
    """Return a 0-100 setup score and a coarse quality label."""
    score = 0.0

    score += min(max(float(getattr(ind, "confidence", 0) or 0), 0.0), 100.0) * 0.35
    score += min(max(float(getattr(ind, "breakout_score", 0) or 0), 0.0), 100.0) * 0.20

    regime = getattr(getattr(ind, "regime", None), "value", getattr(ind, "regime", ""))
    if "alta" in str(regime):
        score += 15.0
    elif "lateral" in str(regime):
        score += 7.0
    elif "baixa" in str(regime):
        score -= 10.0

    volume_ratio = getattr(ind, "volume_ratio", None)
    if volume_ratio is not None:
        score += min(float(volume_ratio), 2.0) / 2.0 * 10.0
    if getattr(ind, "price_above_vwap", False):
        score += 7.0

    if mtf_bias in ("bullish", "alta", "trend_up"):
        score += 8.0
    elif mtf_bias in ("bearish", "baixa", "trend_down"):
        score -= 8.0

    score -= max(0, confidence_adjustment) * 0.5
    score = round(min(max(score, 0.0), 100.0), 2)

    if score >= 80:
        quality = "excellent"
    elif score >= 65:
        quality = "strong"
    elif score >= 45:
        quality = "medium"
    else:
        quality = "weak"

    return {"setup_score": score, "setup_quality": quality}
