# KamiDeep6 — GCQ6 Live Trading Dashboard

Real-time order-flow analytics dashboard for **GCQ6** (Gold Futures Aug-2026) using
Bookmap / Rithmic market data.  Runs in **mock** (simulation) or **live** mode.

---

## Architecture

```
┌─────────────────────────────────┐      HTTP / WebSocket
│  FastAPI Backend  (port 8000)   │ ◄──────────────────────►  Streamlit Frontend
│  • Mock market simulator        │                            (port 8501)
│  • Bookmap / Rithmic WS client  │
│  • All analytics modules        │
└─────────────────────────────────┘
```

## Metrics computed

| Metric | Description |
|---|---|
| **Current Price** | Latest traded price for GCQ6 |
| **Support / Resistance** | Volume-at-price clusters above/below current price |
| **COB Imbalance** | Centre-of-book bid/ask imbalance (top 3 levels) |
| **DOM Imbalance** | Full visible depth bid/ask imbalance |
| **CVD** | Cumulative Volume Delta (running buy − sell volume) |
| **CVD Slope** | Short-term CVD momentum (linear regression slope) |
| **Trend** | EMA-9 / EMA-21 crossover direction |
| **Aggressive Buyer/Seller** | Large market orders lifting ask / hitting bid |
| **Iceberg** | Repeated small prints at same price with large cumulative volume |
| **Absorption** | Large limit orders absorbing aggression without price movement |
| **Signal** | `LONG` / `SHORT` / `NO_TRADE` with confidence % |

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set MODE=mock for simulation, MODE=live for real data
```

### 3. Start the backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start the frontend (separate terminal)

```bash
streamlit run frontend/app.py
```

Open **http://localhost:8501** in your browser.

---

## Live mode (Rithmic / Bookmap)

Set the following in `.env`:

```ini
MODE=live
RITHMIC_WS_URL=wss://your-gateway:443
RITHMIC_USER=your_username
RITHMIC_PASSWORD=your_password
```

> **Note**: Live mode requires the official Rithmic Python SDK and valid
> credentials.  The `BookmapClient` class (`backend/bookmap_client.py`)
> provides the correct interface; adapt the Protobuf parsing methods once you
> have the SDK installed.

---

## Project structure

```
backend/
├── main.py              # FastAPI app (REST + WebSocket)
├── config.py            # Settings (live/mock, symbol, credentials)
├── models.py            # Pydantic data models
├── mock_data.py         # Realistic GCQ6 market simulator
├── bookmap_client.py    # Rithmic / Bookmap WebSocket client
└── analytics/
    ├── support_resistance.py
    ├── dom_imbalance.py
    ├── cvd.py
    ├── trend.py
    ├── aggressive.py
    ├── iceberg.py
    ├── absorption.py
    └── signal.py        # Final LONG/SHORT/NO_TRADE signal generator
frontend/
└── app.py               # Streamlit dashboard
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/config` | Current mode & symbol |
| `GET` | `/metrics` | Latest `MarketMetrics` snapshot (JSON) |
| `WS`  | `/ws/metrics` | Streaming `MarketMetrics` at 1 Hz |
