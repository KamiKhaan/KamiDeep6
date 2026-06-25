"""Trend detection using dual EMA crossover on the trade price series."""
from __future__ import annotations

from backend.models import Trade

FAST_PERIOD = 9
SLOW_PERIOD = 21
_ALPHA_FAST = 2.0 / (FAST_PERIOD + 1)
_ALPHA_SLOW = 2.0 / (SLOW_PERIOD + 1)

_ema_fast: float | None = None
_ema_slow: float | None = None


def update(trades: list[Trade]) -> tuple[str, float, float]:
    """Return (trend, ema_fast, ema_slow).

    trend is "UP", "DOWN", or "NEUTRAL".
    """
    global _ema_fast, _ema_slow

    if not trades:
        p = 0.0
        return "NEUTRAL", p, p

    for t in trades:
        p = t.price
        if _ema_fast is None:
            _ema_fast = p
            _ema_slow = p
        else:
            _ema_fast = _ema_fast + _ALPHA_FAST * (p - _ema_fast)
            _ema_slow = _ema_slow + _ALPHA_SLOW * (p - _ema_slow)

    fast = round(_ema_fast, 2)  # type: ignore[arg-type]
    slow = round(_ema_slow, 2)  # type: ignore[arg-type]

    if fast > slow * 1.0001:
        trend = "UP"
    elif fast < slow * 0.9999:
        trend = "DOWN"
    else:
        trend = "NEUTRAL"

    return trend, fast, slow


def reset() -> None:
    global _ema_fast, _ema_slow
    _ema_fast = None
    _ema_slow = None
