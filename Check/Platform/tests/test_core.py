"""Minimal unit tests for CHECK Platform v4."""

from __future__ import annotations

from app.atr import atr, sanitize
from app.strategy import evaluate


def test_atr_and_sanitize() -> None:
    bars = []
    price = 1.10
    for i in range(40):
        bars.append({"o": price, "h": price + 0.0008, "l": price - 0.0005, "c": price + 0.0002, "v": 1})
        price += 0.0001
    a = atr(bars, 14)
    assert a is not None and a > 0
    assert sanitize(0.05, 1.10) < 0.01


def test_breakout_signal() -> None:
    bars = []
    for _ in range(35):
        bars.append({"o": 1.1000, "h": 1.1008, "l": 1.0992, "c": 1.1000, "v": 1})
    bars.append({"o": 1.1000, "h": 1.1025, "l": 1.1000, "c": 1.1022, "v": 1})
    market = {"bars_m1": bars, "bid": 1.1021, "ask": 1.1022, "symbol": "EURUSD"}
    settings = {"breakout": True, "trend": False, "force_idle": False, "sl_atr": 1.0}
    sig = evaluate(market, settings)
    assert sig is not None
    assert sig.side == "BUY"
