"""GCQ6 Live Trading Dashboard — Streamlit frontend.

Run with:
    streamlit run frontend/app.py

The dashboard polls the FastAPI backend every REFRESH_INTERVAL_MS milliseconds
and renders all market metrics with colour-coded indicators.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
REFRESH_MS = int(os.getenv("REFRESH_INTERVAL_MS", "1000"))

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GCQ6 Live Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .metric-card {
            background: #1e1e2e;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 8px;
        }
        .signal-LONG    { color: #00e676; font-weight: 800; font-size: 2.2rem; }
        .signal-SHORT   { color: #ff5252; font-weight: 800; font-size: 2.2rem; }
        .signal-NO_TRADE{ color: #ffd740; font-weight: 800; font-size: 2.2rem; }
        .badge-UP       { color: #00e676; }
        .badge-DOWN     { color: #ff5252; }
        .badge-NEUTRAL  { color: #9e9e9e; }
        .reason-list    { font-size: 0.85rem; color: #ccc; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Data fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=0.9)
def fetch_metrics() -> dict[str, Any] | None:
    try:
        resp = httpx.get(f"{API_BASE}/metrics", timeout=3.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Could not reach API at {API_BASE}: {exc}")
        return None


@st.cache_data(ttl=30)
def fetch_config() -> dict[str, Any]:
    try:
        resp = httpx.get(f"{API_BASE}/config", timeout=3.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {"mode": "unknown", "symbol": "GCQ6", "exchange": "CME"}


# ── Helper renderers ──────────────────────────────────────────────────────────

def _bool_badge(val: bool, true_label: str = "✅", false_label: str = "—") -> str:
    return true_label if val else false_label


def _imbalance_bar(val: float) -> str:
    """Return a simple ASCII progress bar for an imbalance in [-1, +1]."""
    filled = int((val + 1) / 2 * 20)
    bar = "█" * filled + "░" * (20 - filled)
    return f"`[{bar}]` {val:+.3f}"


def _signal_html(sig: str, conf: float) -> str:
    return (
        f'<span class="signal-{sig}">{sig}</span> '
        f'<span style="font-size:1.2rem; color:#ccc;">({conf:.1f}% confidence)</span>'
    )


# ── Main layout ───────────────────────────────────────────────────────────────

def render(data: dict[str, Any], cfg: dict[str, Any]) -> None:
    mode_badge = (
        "🟢 **LIVE**" if cfg.get("mode") == "live" else "🟡 **MOCK** (simulation)"
    )
    st.title(f"📈 GCQ6 — Gold Futures Aug-2026   {mode_badge}")
    ts = data.get("timestamp", time.time())
    st.caption(
        f"Last update: {time.strftime('%H:%M:%S', time.localtime(ts))} UTC  |  "
        f"Symbol: {data.get('symbol', 'GCQ6')}  |  Exchange: {cfg.get('exchange', 'CME')}"
    )

    # ── Row 1: Price + Signal ──────────────────────────────────────────────────
    col_price, col_signal = st.columns([1, 2])

    with col_price:
        st.metric(
            label="Current Price",
            value=f"${data['current_price']:,.2f}",
        )
        st.metric("Support", f"${data['support']:,.2f}")
        st.metric("Resistance", f"${data['resistance']:,.2f}")

    with col_signal:
        st.markdown("### Final Signal")
        sig = data["signal"]
        conf = data["confidence"]
        st.markdown(_signal_html(sig, conf), unsafe_allow_html=True)
        st.markdown("**Signal Reasons:**")
        reasons = data.get("signal_reasons", [])
        if reasons:
            for r in reasons:
                st.markdown(f"- {r}")
        else:
            st.markdown("_No strong directional factors detected._")

    st.divider()

    # ── Row 2: DOM / COB + CVD + Trend ────────────────────────────────────────
    col_dom, col_cvd, col_trend = st.columns(3)

    with col_dom:
        st.markdown("### 📊 DOM / COB Imbalance")
        st.markdown("**COB (Top-of-Book)**")
        st.markdown(_imbalance_bar(data["cob_imbalance"]))
        st.markdown("**DOM (Full Depth)**")
        st.markdown(_imbalance_bar(data["dom_imbalance"]))

    with col_cvd:
        st.markdown("### 📉 Cumulative Volume Delta")
        cvd_val = data["cvd"]
        cvd_slope = data["cvd_slope"]
        color = "#00e676" if cvd_val >= 0 else "#ff5252"
        st.markdown(
            f'<span style="color:{color}; font-size:1.8rem; font-weight:700;">'
            f'{cvd_val:+,.0f}</span>',
            unsafe_allow_html=True,
        )
        slope_color = "#00e676" if cvd_slope >= 0 else "#ff5252"
        st.markdown(
            f'Slope: <span style="color:{slope_color};">{cvd_slope:+.2f}</span>',
            unsafe_allow_html=True,
        )

    with col_trend:
        st.markdown("### 📈 Trend (EMA)")
        trend_val = data["trend"]
        badge_class = f"badge-{trend_val}"
        arrow = {"UP": "▲", "DOWN": "▼", "NEUTRAL": "◆"}.get(trend_val, "◆")
        st.markdown(
            f'<span class="{badge_class}" style="font-size:1.6rem;">'
            f'{arrow} {trend_val}</span>',
            unsafe_allow_html=True,
        )
        st.metric("EMA Fast", f"{data['ema_fast']:,.2f}")
        st.metric("EMA Slow", f"{data['ema_slow']:,.2f}")

    st.divider()

    # ── Row 3: Aggressive / Iceberg / Absorption ──────────────────────────────
    col_agg, col_ice, col_abs = st.columns(3)

    with col_agg:
        st.markdown("### 🦁 Aggressive Orders")
        agg_buy = data["aggressive_buyer"]
        agg_sell = data["aggressive_seller"]
        buy_vol = data["aggressive_buy_volume"]
        sell_vol = data["aggressive_sell_volume"]

        if agg_buy:
            st.markdown(
                f'<span style="color:#00e676;">🟢 Aggressive BUYER  ({buy_vol} contracts)</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("🔵 No aggressive buyer")

        if agg_sell:
            st.markdown(
                f'<span style="color:#ff5252;">🔴 Aggressive SELLER ({sell_vol} contracts)</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("🔵 No aggressive seller")

    with col_ice:
        st.markdown("### 🧊 Iceberg Orders")
        if data["iceberg_detected"]:
            ice_side = data.get("iceberg_side", "?")
            ice_px = data.get("iceberg_price")
            color = "#00e676" if ice_side == "buy" else "#ff5252"
            label = ice_side.upper() if ice_side else "?"
            st.markdown(
                f'<span style="color:{color};">⚠️ Iceberg {label} @ ${ice_px:,.2f}</span>'
                if ice_px else f'<span style="color:{color};">⚠️ Iceberg {label}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("— No iceberg detected")

    with col_abs:
        st.markdown("### 🧱 Absorption")
        if data["absorption_detected"]:
            abs_side = data.get("absorption_side", "?")
            abs_px = data.get("absorption_price")
            color = "#00e676" if abs_side == "buy" else "#ff5252"
            label = abs_side.upper() if abs_side else "?"
            st.markdown(
                f'<span style="color:{color};">⚠️ Absorbing {label}-side @ ${abs_px:,.2f}</span>'
                if abs_px else f'<span style="color:{color};">⚠️ Absorbing {label}-side</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("— No absorption detected")

    st.divider()
    st.caption(
        "Data refreshes every second. "
        "Set MODE=live in .env to connect to Rithmic / Bookmap gateway."
    )


# ── Auto-refresh loop ─────────────────────────────────────────────────────────

def main() -> None:
    cfg = fetch_config()
    data = fetch_metrics()

    if data is None:
        st.warning(
            "⚠️  Cannot connect to the API backend.  "
            "Start it with:  `uvicorn backend.main:app --reload`"
        )
        st.stop()

    render(data, cfg)

    # Streamlit auto-rerun via experimental_rerun + sleep
    time.sleep(REFRESH_MS / 1000)
    st.rerun()


main()
