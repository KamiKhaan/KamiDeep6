"""COB (Centre-of-Book) and DOM (Depth-of-Market) imbalance.

Imbalance formula: (bid_qty - ask_qty) / (bid_qty + ask_qty)
  * +1.0 = all bids, strong buy pressure
  * -1.0 = all asks, strong sell pressure
"""
from __future__ import annotations

from backend.models import DOMSnapshot

COB_LEVELS = 3   # levels used for centre-of-book calculation


def calculate(dom: DOMSnapshot) -> tuple[float, float]:
    """Return (cob_imbalance, dom_imbalance) each in [-1, +1]."""
    cob_bids = sum(lvl.bid_size for lvl in dom.bids[:COB_LEVELS])
    cob_asks = sum(lvl.ask_size for lvl in dom.asks[:COB_LEVELS])
    cob_imb = _ratio(cob_bids, cob_asks)

    dom_bids = sum(lvl.bid_size for lvl in dom.bids)
    dom_asks = sum(lvl.ask_size for lvl in dom.asks)
    dom_imb = _ratio(dom_bids, dom_asks)

    return round(cob_imb, 4), round(dom_imb, 4)


def _ratio(b: int, a: int) -> float:
    total = b + a
    if total == 0:
        return 0.0
    return (b - a) / total
