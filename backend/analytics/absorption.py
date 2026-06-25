"""Absorption detector.

Absorption occurs when large aggressive trades hit a price level but price
does NOT move (the limit orders are absorbing the aggression).

Heuristic:
* Look at the DOM history for a specific price level.
* If that level had significant size in the DOM *and* has absorbed large
  aggressive volume (from the trade tape) yet the price has not moved past
  that level, flag absorption.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from backend.models import DOMSnapshot, Trade

WINDOW_SECONDS = 8.0
ABSORBED_VOL_THRESHOLD = 60   # total aggressive volume that was absorbed
PRICE_MOVE_LIMIT = 0.30        # max price movement allowed (in $) for absorption


def detect(
    trades: list[Trade],
    dom_history: list[DOMSnapshot],
    current_price: float,
) -> tuple[bool, Optional[str], Optional[float]]:
    """Return (detected, side, price)."""
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    # Aggregate aggressive volume by price
    buy_vol: dict[float, int] = defaultdict(int)
    sell_vol: dict[float, int] = defaultdict(int)
    prices_seen: list[float] = []

    for t in trades:
        if t.timestamp < cutoff:
            continue
        if t.side == "buy":
            buy_vol[t.price] += t.size
        else:
            sell_vol[t.price] += t.size
        prices_seen.append(t.price)

    if not prices_seen:
        return False, None, None

    price_range = max(prices_seen) - min(prices_seen)
    if price_range > PRICE_MOVE_LIMIT:
        # Price has moved significantly — no absorption
        return False, None, None

    # Check sell-side absorption: sellers hitting a bid that holds
    for price, vol in sell_vol.items():
        if vol >= ABSORBED_VOL_THRESHOLD and abs(price - current_price) < PRICE_MOVE_LIMIT:
            return True, "buy", round(price, 2)   # buy-side absorbing selling

    # Check buy-side absorption: buyers lifting an ask that holds
    for price, vol in buy_vol.items():
        if vol >= ABSORBED_VOL_THRESHOLD and abs(price - current_price) < PRICE_MOVE_LIMIT:
            return True, "sell", round(price, 2)  # sell-side absorbing buying

    return False, None, None
