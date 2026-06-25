"""Final trading signal generator.

Combines all individual metrics into a single LONG / SHORT / NO_TRADE signal
with an associated confidence percentage (0–100 %).

Each factor contributes a signed score in [-1, +1].  Weights are chosen to
reflect the relative reliability / importance of each signal component.

  Score >  LONG_THRESHOLD  → LONG
  Score < -LONG_THRESHOLD  → SHORT
  Otherwise                → NO_TRADE
"""
from __future__ import annotations

LONG_THRESHOLD = 0.20   # minimum |score| to commit to a directional trade

# Factor weights (must sum to 1.0 for confidence normalisation)
WEIGHTS = {
    "dom_imbalance":      0.20,
    "cob_imbalance":      0.15,
    "cvd_slope":          0.20,
    "trend":              0.20,
    "aggressive":         0.10,
    "iceberg":            0.08,
    "absorption":         0.07,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


def generate(
    dom_imbalance: float,
    cob_imbalance: float,
    cvd_slope: float,
    trend: str,
    aggressive_buyer: bool,
    aggressive_seller: bool,
    iceberg_detected: bool,
    iceberg_side: str | None,
    absorption_detected: bool,
    absorption_side: str | None,
    current_price: float,
    support: float,
    resistance: float,
) -> tuple[str, float, list[str]]:
    """Return (signal, confidence_pct, reasons)."""

    scores: dict[str, float] = {}
    reasons: list[str] = []

    # DOM imbalance: positive → buy pressure
    scores["dom_imbalance"] = float(dom_imbalance)
    if dom_imbalance > 0.15:
        reasons.append(f"DOM imbalance bullish ({dom_imbalance:+.2f})")
    elif dom_imbalance < -0.15:
        reasons.append(f"DOM imbalance bearish ({dom_imbalance:+.2f})")

    # COB imbalance
    scores["cob_imbalance"] = float(cob_imbalance)
    if cob_imbalance > 0.20:
        reasons.append(f"COB imbalance bullish ({cob_imbalance:+.2f})")
    elif cob_imbalance < -0.20:
        reasons.append(f"COB imbalance bearish ({cob_imbalance:+.2f})")

    # CVD slope
    cvd_score = max(-1.0, min(1.0, cvd_slope / 50.0))  # normalise
    scores["cvd_slope"] = cvd_score
    if cvd_score > 0.1:
        reasons.append(f"CVD accelerating upward (slope {cvd_slope:+.1f})")
    elif cvd_score < -0.1:
        reasons.append(f"CVD decelerating / selling (slope {cvd_slope:+.1f})")

    # Trend
    trend_map = {"UP": 1.0, "DOWN": -1.0, "NEUTRAL": 0.0}
    scores["trend"] = trend_map.get(trend, 0.0)
    if trend != "NEUTRAL":
        reasons.append(f"EMA trend: {trend}")

    # Aggressive buyer / seller
    if aggressive_buyer and not aggressive_seller:
        scores["aggressive"] = 1.0
        reasons.append("Aggressive buyer detected")
    elif aggressive_seller and not aggressive_buyer:
        scores["aggressive"] = -1.0
        reasons.append("Aggressive seller detected")
    elif aggressive_buyer and aggressive_seller:
        scores["aggressive"] = 0.0
        reasons.append("Both sides aggressive — mixed signal")
    else:
        scores["aggressive"] = 0.0

    # Iceberg
    if iceberg_detected and iceberg_side:
        scores["iceberg"] = 1.0 if iceberg_side == "buy" else -1.0
        reasons.append(f"Iceberg order detected on {iceberg_side} side")
    else:
        scores["iceberg"] = 0.0

    # Absorption
    if absorption_detected and absorption_side:
        # buy-side absorption → sellers failing → bullish
        scores["absorption"] = 1.0 if absorption_side == "buy" else -1.0
        reasons.append(
            f"Absorption: {absorption_side}-side absorbing pressure"
        )
    else:
        scores["absorption"] = 0.0

    # Price relative to S/R
    sr_range = resistance - support
    if sr_range > 0:
        relative_pos = (current_price - support) / sr_range  # 0..1
        if relative_pos < 0.25:
            reasons.append("Price near support level — potential reversal up")
        elif relative_pos > 0.75:
            reasons.append("Price near resistance — potential reversal down")

    # Weighted composite score
    total = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS)

    if total > LONG_THRESHOLD:
        signal = "LONG"
    elif total < -LONG_THRESHOLD:
        signal = "SHORT"
    else:
        signal = "NO_TRADE"

    # Confidence: map |total| → 0..100 %
    confidence = round(min(100.0, abs(total) / 1.0 * 100), 1)

    if not reasons:
        reasons.append("No strong directional factors")

    return signal, confidence, reasons
