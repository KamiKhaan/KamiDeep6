"""Iceberg order detector.

Iceberg signature: many small trades at the *same* price level within a short
window, where the cumulative volume is large despite each individual print
being small (the hidden portion keeps refreshing).

Detection logic:
1. Group recent trades by price.
2. For each price: count prints and sum volume.
3. An iceberg is flagged when count >= MIN_PRINTS and total_vol >= MIN_TOTAL_VOL
   but average_size <= MAX_AVG_SIZE (ensuring prints are individually small).
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import List, Optional, Tuple

from backend.models import Trade

WINDOW_SECONDS = 10.0
MIN_PRINTS = 6
MIN_TOTAL_VOL = 40
MAX_AVG_SIZE = 8


def detect(
    trades: List[Trade],
) -> Tuple[bool, Optional[str], Optional[float]]:
    """Return (detected, side, price)."""
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    # price -> {side -> {count, volume}}
    stats: dict[float, dict[str, dict[str, int]]] = defaultdict(
        lambda: {"buy": {"count": 0, "vol": 0}, "sell": {"count": 0, "vol": 0}}
    )

    for t in trades:
        if t.timestamp < cutoff:
            continue
        stats[t.price][t.side]["count"] += 1
        stats[t.price][t.side]["vol"] += t.size

    for price, sides in stats.items():
        for side, data in sides.items():
            count = data["count"]
            vol = data["vol"]
            if count == 0:
                continue
            avg = vol / count
            if count >= MIN_PRINTS and vol >= MIN_TOTAL_VOL and avg <= MAX_AVG_SIZE:
                return True, side, price

    return False, None, None
