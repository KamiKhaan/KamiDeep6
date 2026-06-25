"""Support and resistance detection.

Uses a volume-at-price profile computed from the recent trade tape to identify
the two most significant price clusters (support below, resistance above
the current price).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Tuple

from backend.models import Trade

TICK_SIZE = 0.10
LOOKBACK = 300  # trades


def detect(trades: list[Trade], current_price: float) -> tuple[float, float]:
    """Return (support, resistance) price levels."""
    if not trades:
        return current_price - 2.0, current_price + 2.0

    recent = trades[-LOOKBACK:]

    # Build volume-at-price histogram (round to tick grid)
    vap: dict[float, int] = defaultdict(int)
    for t in recent:
        p = round(t.price / TICK_SIZE) * TICK_SIZE
        vap[p] = vap[p] + t.size

    # Split into below / above current price
    below = {p: v for p, v in vap.items() if p < current_price}
    above = {p: v for p, v in vap.items() if p > current_price}

    if below:
        support = max(below, key=lambda p: below[p])
    else:
        support = current_price - 2.0 * TICK_SIZE

    if above:
        resistance = max(above, key=lambda p: above[p])
    else:
        resistance = current_price + 2.0 * TICK_SIZE

    return round(support, 2), round(resistance, 2)
