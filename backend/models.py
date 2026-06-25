from __future__ import annotations

from pydantic import BaseModel, Field


class PriceLevel(BaseModel):
    price: float
    bid_size: int
    ask_size: int


class Trade(BaseModel):
    price: float
    size: int
    side: str  # "buy" | "sell"
    timestamp: float  # Unix epoch seconds


class DOMSnapshot(BaseModel):
    """Full depth-of-market snapshot (up to N levels each side)."""
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    timestamp: float


class MarketMetrics(BaseModel):
    symbol: str = "GCQ6"
    mode: str = "mock"
    timestamp: float

    # ── Price ─────────────────────────────────────────────────────────────────
    current_price: float

    # ── Support / Resistance ──────────────────────────────────────────────────
    support: float
    resistance: float

    # ── DOM / COB imbalance ───────────────────────────────────────────────────
    # Range [-1, +1]. Positive = more bids (buying pressure).
    cob_imbalance: float = Field(ge=-1.0, le=1.0)   # top-of-book (best bid/ask)
    dom_imbalance: float = Field(ge=-1.0, le=1.0)   # full visible depth

    # ── Cumulative Volume Delta ────────────────────────────────────────────────
    cvd: float          # running total (positive = net buying)
    cvd_slope: float    # short-term slope (sign indicates momentum direction)

    # ── Trend ─────────────────────────────────────────────────────────────────
    trend: str          # "UP" | "DOWN" | "NEUTRAL"
    ema_fast: float
    ema_slow: float

    # ── Aggressive prints ─────────────────────────────────────────────────────
    aggressive_buyer: bool    # large aggressive buy in last window
    aggressive_seller: bool   # large aggressive sell in last window
    aggressive_buy_volume: int
    aggressive_sell_volume: int

    # ── Iceberg detection ─────────────────────────────────────────────────────
    iceberg_detected: bool
    iceberg_side: str | None = None   # "buy" | "sell" | None
    iceberg_price: float | None = None

    # ── Absorption ────────────────────────────────────────────────────────────
    absorption_detected: bool
    absorption_side: str | None = None   # "buy" | "sell" | None
    absorption_price: float | None = None

    # ── Final signal ──────────────────────────────────────────────────────────
    signal: str              # "LONG" | "SHORT" | "NO_TRADE"
    confidence: float        # 0–100 %
    signal_reasons: list[str]
