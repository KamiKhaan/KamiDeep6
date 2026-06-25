"""Cumulative Volume Delta (CVD) calculator.

CVD = running sum of (buy_volume - sell_volume).
A rising CVD indicates net aggressive buying; falling = net aggressive selling.
cvd_slope is computed as the simple linear regression slope over the last
`SLOPE_WINDOW` data points (positive = accelerating buy pressure).
"""
from __future__ import annotations

from collections import deque
from typing import List, Tuple

import numpy as np

from backend.models import Trade

SLOPE_WINDOW = 30   # trades used for slope estimation

# Module-level running state
_cvd: float = 0.0
_cvd_series: deque[float] = deque(maxlen=SLOPE_WINDOW)
_last_processed: int = 0   # index into trade list we've consumed up to


def update(trades: List[Trade]) -> Tuple[float, float]:
    """Consume any new trades and return (cvd, cvd_slope)."""
    global _cvd, _last_processed

    new_trades = trades[_last_processed:]
    _last_processed = len(trades)

    for t in new_trades:
        delta = t.size if t.side == "buy" else -t.size
        _cvd += delta
        _cvd_series.append(_cvd)

    slope = _compute_slope(list(_cvd_series))
    return round(_cvd, 1), round(slope, 4)


def _compute_slope(series: List[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    y = np.array(series, dtype=float)
    # Least-squares slope
    xm, ym = x.mean(), y.mean()
    denom = float(np.sum((x - xm) ** 2))
    if denom == 0:
        return 0.0
    return float(np.sum((x - xm) * (y - ym)) / denom)


def reset() -> None:
    """Reset all state (useful for tests / reconnect)."""
    global _cvd, _last_processed
    _cvd = 0.0
    _last_processed = 0
    _cvd_series.clear()
