"""Realistic intraday mock-data generator for GCQ6 (Gold Aug-2026 futures).

The generator maintains a live order book and a trade tape that evolve each
tick so all downstream analytics modules have coherent input data.
"""
from __future__ import annotations

import math
import random
import time
from collections import deque
from typing import Deque, List

from backend.models import DOMSnapshot, PriceLevel, Trade

# ── Constants ─────────────────────────────────────────────────────────────────
TICK_SIZE = 0.10          # GCQ6 minimum price increment
BASE_PRICE = 2_380.0      # approximate mid-price at session start
DOM_LEVELS = 10           # visible depth levels each side
TRADE_HISTORY = 500       # number of trades to keep in memory
DOM_HISTORY = 200         # number of DOM snapshots to keep


class MockMarket:
    """Stateful mock market for GCQ6."""

    def __init__(self) -> None:
        self._mid = BASE_PRICE
        self._spread = TICK_SIZE * 2
        self._vol_regime = 1.0          # 0.5 = quiet, 2.0 = volatile
        self._trend_bias = 0.0          # -1..+1 drifts price slowly
        self._regime_counter = 0

        self.trades: Deque[Trade] = deque(maxlen=TRADE_HISTORY)
        self.dom_history: Deque[DOMSnapshot] = deque(maxlen=DOM_HISTORY)

        # Iceberg / absorption state
        self._iceberg_price: float | None = None
        self._iceberg_side: str | None = None
        self._iceberg_ticks_left: int = 0

        self._absorption_price: float | None = None
        self._absorption_side: str | None = None
        self._absorption_ticks_left: int = 0

        # Seed initial data
        for _ in range(60):
            self._tick(fast=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self) -> tuple[DOMSnapshot, List[Trade]]:
        """Advance the market by one simulation step and return current state."""
        self._tick()
        snap = self._build_dom()
        self.dom_history.append(snap)
        return snap, list(self.trades)

    @property
    def mid(self) -> float:
        return self._mid

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _tick(self, fast: bool = False) -> None:
        """Single simulation step."""
        self._regime_counter += 1
        if self._regime_counter % 120 == 0:
            self._vol_regime = random.uniform(0.5, 2.5)
            self._trend_bias = random.uniform(-0.6, 0.6)

        # Price walk
        drift = self._trend_bias * TICK_SIZE * 0.3
        noise = random.gauss(0, TICK_SIZE * self._vol_regime * 0.5)
        self._mid = round(
            (self._mid + drift + noise) / TICK_SIZE
        ) * TICK_SIZE
        self._mid = max(2_200.0, min(2_600.0, self._mid))

        # Generate 1-5 trades per tick
        n_trades = 1 if fast else random.randint(1, 5)
        for _ in range(n_trades):
            self._gen_trade()

        # Occasionally inject iceberg or absorption event
        if not fast:
            if self._iceberg_ticks_left <= 0 and random.random() < 0.03:
                self._iceberg_price = self._mid
                self._iceberg_side = random.choice(["buy", "sell"])
                self._iceberg_ticks_left = random.randint(10, 30)
            if self._iceberg_ticks_left > 0:
                self._iceberg_ticks_left -= 1
                self._gen_iceberg_trade()

            if self._absorption_ticks_left <= 0 and random.random() < 0.025:
                self._absorption_price = self._mid - (
                    TICK_SIZE if self._trend_bias > 0 else -TICK_SIZE
                )
                self._absorption_side = "buy" if self._trend_bias > 0 else "sell"
                self._absorption_ticks_left = random.randint(8, 20)
            if self._absorption_ticks_left > 0:
                self._absorption_ticks_left -= 1

    def _gen_trade(self) -> None:
        side = "buy" if random.random() > 0.5 - self._trend_bias * 0.1 else "sell"
        # Occasional large aggressive print
        if random.random() < 0.04:
            size = random.randint(50, 200)
        else:
            size = random.randint(1, 20)
        offset = 0 if side == "buy" else -TICK_SIZE
        price = round((self._mid + offset) / TICK_SIZE) * TICK_SIZE
        self.trades.append(
            Trade(price=price, size=size, side=side, timestamp=time.time())
        )

    def _gen_iceberg_trade(self) -> None:
        if self._iceberg_price is None or self._iceberg_side is None:
            return
        # Small consistent prints at same price = iceberg signature
        size = random.randint(1, 5)
        self.trades.append(
            Trade(
                price=self._iceberg_price,
                size=size,
                side=self._iceberg_side,
                timestamp=time.time(),
            )
        )

    def _build_dom(self) -> DOMSnapshot:
        bids: List[PriceLevel] = []
        asks: List[PriceLevel] = []
        best_bid = round((self._mid - TICK_SIZE) / TICK_SIZE) * TICK_SIZE
        best_ask = round((self._mid + TICK_SIZE) / TICK_SIZE) * TICK_SIZE

        for i in range(DOM_LEVELS):
            # Volume shape: higher near top-of-book, tails off deeper
            base = max(1, int(200 / (i + 1) * self._vol_regime + random.randint(0, 30)))
            # Imbalance injection
            imb = 1.0 + self._trend_bias * 0.5
            bids.append(
                PriceLevel(
                    price=round(best_bid - i * TICK_SIZE, 2),
                    bid_size=max(1, int(base * imb)),
                    ask_size=0,
                )
            )
            asks.append(
                PriceLevel(
                    price=round(best_ask + i * TICK_SIZE, 2),
                    bid_size=0,
                    ask_size=max(1, int(base / imb)),
                )
            )

        return DOMSnapshot(bids=bids, asks=asks, timestamp=time.time())


# Module-level singleton so all parts of the app share the same state
_market: MockMarket | None = None


def get_mock_market() -> MockMarket:
    global _market
    if _market is None:
        _market = MockMarket()
    return _market
