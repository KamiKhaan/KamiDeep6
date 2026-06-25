"""Aggressive buyer / seller detector.

An 'aggressive buyer' is a market participant who lifts the ask with
a large order. We detect this by scanning trades in a rolling time window
for trades on the 'buy' side whose size exceeds the threshold.

Similarly for aggressive sellers hitting the bid.
"""
from __future__ import annotations

import time

from backend.models import Trade

WINDOW_SECONDS = 5.0   # rolling window
SIZE_THRESHOLD = 30    # contracts per single trade to qualify


def detect(trades: list[Trade]) -> tuple[bool, bool, int, int]:
    """Return (aggressive_buyer, aggressive_seller, buy_vol, sell_vol).

    Only trades within the last WINDOW_SECONDS are considered.
    """
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    buy_vol = 0
    sell_vol = 0
    for t in reversed(trades):
        if t.timestamp < cutoff:
            break
        if t.side == "buy" and t.size >= SIZE_THRESHOLD:
            buy_vol += t.size
        elif t.side == "sell" and t.size >= SIZE_THRESHOLD:
            sell_vol += t.size

    return buy_vol > 0, sell_vol > 0, buy_vol, sell_vol
