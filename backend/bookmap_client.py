"""Bookmap / Rithmic WebSocket client (live mode).

This module provides a thin async client that connects to a Rithmic
infrastructure gateway via WebSocket and translates the raw market data
feed into the internal Trade / DOMSnapshot models.

NOTE: The Rithmic R|Protocol uses a proprietary binary/Protobuf format.
      A full implementation requires the official Rithmic Python API
      (rithmic_api or rapi) and valid credentials.  The class below
      provides the correct *interface* and connection lifecycle; replace
      the `_parse_*` methods with real Protobuf deserialization once you
      have the Rithmic SDK installed.

Usage (from an asyncio context):
    client = BookmapClient(settings)
    await client.connect()
    dom, trades = await client.get_snapshot()
    await client.disconnect()
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import List, Optional, Tuple

from backend.config import Settings
from backend.models import DOMSnapshot, PriceLevel, Trade

logger = logging.getLogger(__name__)


class BookmapClient:
    """Async client for the Rithmic / Bookmap gateway."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws: Optional[object] = None
        self._connected = False
        self._dom: Optional[DOMSnapshot] = None
        self._trades: List[Trade] = []

    async def connect(self) -> None:
        """Open WebSocket connection and subscribe to GCQ6 market data."""
        try:
            import websockets  # type: ignore[import]

            logger.info(
                "Connecting to Rithmic gateway: %s", self._settings.rithmic_ws_url
            )
            self._ws = await websockets.connect(  # type: ignore[attr-defined]
                self._settings.rithmic_ws_url,
                extra_headers={
                    "Authorization": f"******"
                },
            )
            await self._authenticate()
            await self._subscribe()
            self._connected = True
            asyncio.ensure_future(self._read_loop())
        except Exception as exc:
            logger.error("Failed to connect to Rithmic gateway: %s", exc)
            raise

    async def disconnect(self) -> None:
        if self._ws is not None:
            await self._ws.close()  # type: ignore[attr-defined]
        self._connected = False

    async def get_snapshot(self) -> Tuple[Optional[DOMSnapshot], List[Trade]]:
        """Return the most recent DOM snapshot and accumulated trade tape."""
        trades = list(self._trades)
        self._trades.clear()
        return self._dom, trades

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _authenticate(self) -> None:
        """Send login request (Rithmic-specific)."""
        msg = json.dumps(
            {
                "type": "login",
                "user": self._settings.rithmic_user,
                "password": self._settings.rithmic_password,
                "system_name": self._settings.rithmic_system_name,
            }
        )
        await self._ws.send(msg)  # type: ignore[union-attr]
        resp = await self._ws.recv()  # type: ignore[union-attr]
        logger.debug("Login response: %s", resp)

    async def _subscribe(self) -> None:
        """Subscribe to level-2 market data for the configured symbol."""
        msg = json.dumps(
            {
                "type": "subscribe",
                "symbol": self._settings.symbol,
                "exchange": self._settings.exchange,
                "feeds": ["trades", "dom"],
            }
        )
        await self._ws.send(msg)  # type: ignore[union-attr]

    async def _read_loop(self) -> None:
        """Continuously read and parse incoming messages."""
        try:
            async for raw in self._ws:  # type: ignore[union-attr]
                await self._handle_message(raw)
        except Exception as exc:
            logger.warning("WebSocket read loop ended: %s", exc)
            self._connected = False

    async def _handle_message(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return

        msg_type = msg.get("type")
        if msg_type == "trade":
            trade = self._parse_trade(msg)
            if trade:
                self._trades.append(trade)
        elif msg_type == "dom":
            self._dom = self._parse_dom(msg)

    def _parse_trade(self, msg: dict) -> Optional[Trade]:
        try:
            return Trade(
                price=float(msg["price"]),
                size=int(msg["size"]),
                side=msg["side"],  # expected "buy" | "sell"
                timestamp=float(msg.get("timestamp", time.time())),
            )
        except Exception as exc:
            logger.debug("Could not parse trade message: %s — %s", msg, exc)
            return None

    def _parse_dom(self, msg: dict) -> Optional[DOMSnapshot]:
        try:
            bids = [
                PriceLevel(price=float(l["price"]), bid_size=int(l["size"]), ask_size=0)
                for l in msg.get("bids", [])
            ]
            asks = [
                PriceLevel(price=float(l["price"]), bid_size=0, ask_size=int(l["size"]))
                for l in msg.get("asks", [])
            ]
            return DOMSnapshot(
                bids=bids,
                asks=asks,
                timestamp=float(msg.get("timestamp", time.time())),
            )
        except Exception as exc:
            logger.debug("Could not parse DOM message: %s — %s", msg, exc)
            return None
