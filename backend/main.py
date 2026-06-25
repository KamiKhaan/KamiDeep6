"""FastAPI backend for the GCQ6 live dashboard.

Endpoints
---------
GET  /health                  – liveness probe
GET  /metrics                 – latest MarketMetrics snapshot (JSON)
WS   /ws/metrics              – streaming MarketMetrics over WebSocket (1 Hz)
GET  /config                  – current mode and symbol
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend import analytics  # noqa: F401 — side-effect free, just confirms import
from backend.analytics import (
    absorption,
    aggressive,
    cvd,
    dom_imbalance,
    iceberg,
    signal,
    support_resistance,
    trend,
)
from backend.config import settings
from backend.models import DOMSnapshot, MarketMetrics, Trade

logger = logging.getLogger("gcq6_dashboard")
logging.basicConfig(level=logging.INFO)

# ── Shared state ──────────────────────────────────────────────────────────────
_latest_metrics: MarketMetrics | None = None


# ── Market data provider ──────────────────────────────────────────────────────

async def _fetch_market_data() -> tuple[DOMSnapshot, list[Trade]]:
    """Return the latest DOM snapshot and trade tape (mock or live)."""
    if settings.mode == "mock":
        from backend.mock_data import get_mock_market

        market = get_mock_market()
        return market.update()
    else:
        # Live mode: use the BookmapClient singleton
        from backend.bookmap_client import BookmapClient

        global _bookmap_client  # type: ignore[name-defined]
        snap, trades = await _bookmap_client.get_snapshot()
        if snap is None:
            # Fallback to mock while waiting for first DOM snapshot
            from backend.mock_data import get_mock_market

            market = get_mock_market()
            return market.update()
        return snap, trades


def _compute_metrics(dom: DOMSnapshot, trades: list[Trade]) -> MarketMetrics:
    """Run all analytics and assemble a MarketMetrics object."""
    current_price = dom.asks[0].price if dom.asks else (dom.bids[0].price if dom.bids else 0.0)

    supp, res = support_resistance.detect(trades, current_price)
    cob_imb, dom_imb = dom_imbalance.calculate(dom)
    cvd_val, cvd_sl = cvd.update(trades)
    trend_str, ema_f, ema_s = trend.update(trades)
    agg_buy, agg_sell, agg_buy_vol, agg_sell_vol = aggressive.detect(trades)
    ice_det, ice_side, ice_price = iceberg.detect(trades)

    from backend.mock_data import get_mock_market
    dom_hist = list(get_mock_market().dom_history) if settings.mode == "mock" else []
    abs_det, abs_side, abs_price = absorption.detect(trades, dom_hist, current_price)

    sig, conf, reasons = signal.generate(
        dom_imbalance=dom_imb,
        cob_imbalance=cob_imb,
        cvd_slope=cvd_sl,
        trend=trend_str,
        aggressive_buyer=agg_buy,
        aggressive_seller=agg_sell,
        iceberg_detected=ice_det,
        iceberg_side=ice_side,
        absorption_detected=abs_det,
        absorption_side=abs_side,
        current_price=current_price,
        support=supp,
        resistance=res,
    )

    return MarketMetrics(
        symbol=settings.symbol,
        mode=settings.mode,
        timestamp=time.time(),
        current_price=current_price,
        support=supp,
        resistance=res,
        cob_imbalance=cob_imb,
        dom_imbalance=dom_imb,
        cvd=cvd_val,
        cvd_slope=cvd_sl,
        trend=trend_str,
        ema_fast=ema_f,
        ema_slow=ema_s,
        aggressive_buyer=agg_buy,
        aggressive_seller=agg_sell,
        aggressive_buy_volume=agg_buy_vol,
        aggressive_sell_volume=agg_sell_vol,
        iceberg_detected=ice_det,
        iceberg_side=ice_side,
        iceberg_price=ice_price,
        absorption_detected=abs_det,
        absorption_side=abs_side,
        absorption_price=abs_price,
        signal=sig,
        confidence=conf,
        signal_reasons=reasons,
    )


# ── Background task ───────────────────────────────────────────────────────────

async def _metrics_loop() -> None:
    """Update metrics every second."""
    global _latest_metrics
    while True:
        try:
            dom, trades = await _fetch_market_data()
            _latest_metrics = _compute_metrics(dom, trades)
        except Exception as exc:
            logger.error("Metrics computation error: %s", exc)
        await asyncio.sleep(1.0)


# ── Application lifecycle ─────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _bookmap_client  # type: ignore[name-defined]

    if settings.mode == "live":
        from backend.bookmap_client import BookmapClient

        _bookmap_client = BookmapClient(settings)
        try:
            await _bookmap_client.connect()
        except Exception as exc:
            logger.warning("Live connection failed (%s); falling back to mock.", exc)

    task = asyncio.create_task(_metrics_loop())
    yield
    task.cancel()

    if settings.mode == "live":
        await _bookmap_client.disconnect()


app = FastAPI(
    title="GCQ6 Live Dashboard API",
    version="1.0.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mode": settings.mode, "symbol": settings.symbol}


@app.get("/config")
async def get_config() -> dict:
    return {
        "mode": settings.mode,
        "symbol": settings.symbol,
        "exchange": settings.exchange,
    }


@app.get("/metrics", response_model=MarketMetrics)
async def get_metrics() -> MarketMetrics:
    global _latest_metrics
    if _latest_metrics is None:
        # Compute synchronously on first request before background loop fires
        dom, trades = await _fetch_market_data()
        _latest_metrics = _compute_metrics(dom, trades)
    return _latest_metrics


@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket client connected")
    try:
        while True:
            if _latest_metrics is not None:
                await websocket.send_text(_latest_metrics.model_dump_json())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
