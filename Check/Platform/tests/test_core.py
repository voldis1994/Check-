"""Core strategy/ATR tests."""

from __future__ import annotations

from app.atr import atr, sanitize
from app.strategy import evaluate, manage_sl


def test_atr_and_sanitize() -> None:
    bars = []
    price = 1.10
    for _ in range(40):
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


def test_trail_uses_start_then_lock() -> None:
    settings = {"be_start_atr": 10.0, "be_offset_atr": 0.05, "trail_start_atr": 0.5, "trail_lock_atr": 0.75}
    # profit 0.6 ATR with atr=0.001 → start hit, lock = price - 0.00075
    new_sl = manage_sl("BUY", entry=1.0, price=1.0006, current_sl=0.999, atr_v=0.001, settings=settings)
    assert new_sl is not None
    assert abs(new_sl - (1.0006 - 0.00075)) < 1e-9


def test_force_idle_off_by_default_path() -> None:
    bars = []
    for i in range(40):
        bars.append({"o": 1.1, "h": 1.1005, "l": 1.0995, "c": 1.1 + (0.0002 if i == 39 else 0), "v": 1})
    market = {"bars_m1": bars, "bid": 1.1002, "ask": 1.1003}
    assert evaluate(market, {"breakout": False, "trend": False, "force_idle": False, "sl_atr": 1.0}) is None
