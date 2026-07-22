"""Sample MT4-like JSON payloads for bridge/reader tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

_BASE_TIME = datetime(2026, 1, 10, 9, 0, 0, tzinfo=UTC)


def make_candle_row(
    i: int,
    open_: float = 1.1000,
    drift: float = 0.0001,
    tf: str = "M1",
) -> dict:
    ts = _BASE_TIME + timedelta(minutes=i)
    c = open_ + drift * i
    return {
        "time": ts.isoformat(),
        "open": round(open_ + drift * i, 5),
        "high": round(c + 0.0005, 5),
        "low": round(c - 0.0003, 5),
        "close": round(c + 0.0001, 5),
        "volume": 100 + i,
        "tick_volume": 100 + i,
        "closed": True,
    }


def make_bars_m1(n: int = 20, open_: float = 1.1000) -> list[dict]:
    return [make_candle_row(i, open_=open_) for i in range(n)]


# ── MT4 bridge market/latest.json payload ─────────────────────────────────────
# MT4 EA writes bars_m1 (closed M1 bars) in the payload.
MARKET_LATEST_PAYLOAD: dict = {
    "protocol_version": "3.0.0",
    "message_type": "MARKET_STATUS",
    "timestamp": _BASE_TIME.isoformat(),
    "payload": {
        "symbol": "EURUSD",
        "bid": 1.10520,
        "ask": 1.10525,
        "timestamp": _BASE_TIME.isoformat(),
        "bars_m1": make_bars_m1(30),
    },
}

MARKET_LATEST_JSON: str = json.dumps(MARKET_LATEST_PAYLOAD)

# ── Legacy flat market payload (no envelope) ───────────────────────────────────
MARKET_FLAT_PAYLOAD: dict = {
    "symbol": "EURUSD",
    "bid": 1.10520,
    "ask": 1.10525,
    "timestamp": _BASE_TIME.isoformat(),
    "m1": make_bars_m1(20),
    "m5": [],
    "m15": [],
}

# ── Status payload (bridge_dir/status/latest.json) ─────────────────────────────
STATUS_PAYLOAD: dict = {
    "protocol_version": "3.0.0",
    "message_type": "ACCOUNT_STATUS",
    "timestamp": _BASE_TIME.isoformat(),
    "payload": {
        "account_number": "123456",
        "account_id": "123456",
        "balance": 10000.0,
        "equity": 10050.0,
        "free_margin": 9800.0,
        "currency": "USD",
        "trade_allowed": True,
        "trading_allowed": True,
        "connected": True,
    },
}

# ── Positions payload ──────────────────────────────────────────────────────────
POSITIONS_PAYLOAD: dict = {
    "payload": {
        "positions": [
            {
                "position_id": "pos-001",
                "ticket": "10001",
                "symbol": "EURUSD",
                "side": "BUY",
                "lot": 0.01,
                "entry_price": 1.10200,
                "open_price": 1.10200,
                "stop_loss": 1.09800,
                "take_profit": 1.11000,
                "opened_at": _BASE_TIME.isoformat(),
                "strategy": "TREND_CONTINUATION",
                "current_price": 1.10520,
                "profit": 32.0,
                "magic_number": 30001,
            }
        ]
    }
}

# ── ACK payload ────────────────────────────────────────────────────────────────
ACK_PAYLOAD: dict = {
    "payload": {
        "command_id": "cmd-abc-001",
        "accepted": True,
        "reason": "ACK_ACCEPTED",
        "broker_order_id": "10001",
        "message": "OK",
    }
}
