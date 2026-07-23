"""M1 strategies — trend + breakout only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.atr import atr, sanitize


@dataclass
class Signal:
    side: str  # BUY | SELL
    entry: float
    sl: float
    reason: str


def _ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def evaluate(market: dict[str, Any], settings: dict[str, Any]) -> Signal | None:
    bars = market.get("bars_m1") or []
    if len(bars) < 30:
        return None
    # chronological oldest→newest (EA sends oldest first)
    closes = [float(b["c"]) for b in bars]
    highs = [float(b["h"]) for b in bars]
    lows = [float(b["l"]) for b in bars]
    bid = float(market.get("bid") or closes[-1])
    ask = float(market.get("ask") or closes[-1])
    mid = (bid + ask) / 2 if bid and ask else closes[-1]

    raw = atr(bars, 14)
    if raw is None:
        return None
    a = sanitize(raw, mid)
    sl_mult = float(settings.get("sl_atr") or 1.0)
    stop_d = a * sl_mult

    last = bars[-1]
    prev = bars[-2]
    body = abs(float(last["c"]) - float(last["o"]))

    # --- Breakout: M1 range break of last 20 bars ---
    if settings.get("breakout", True):
        look = bars[-21:-1]
        if len(look) >= 15:
            box_hi = max(float(b["h"]) for b in look)
            box_lo = min(float(b["l"]) for b in look)
            width = box_hi - box_lo
            if width > a * 0.3:
                c = float(last["c"])
                if c > box_hi and c >= float(last["o"]):
                    entry = ask
                    return Signal("BUY", entry, entry - stop_d, "BREAKOUT_UP")
                if c < box_lo and c <= float(last["o"]):
                    entry = bid
                    return Signal("SELL", entry, entry + stop_d, "BREAKOUT_DOWN")

    # --- Trend: EMA20 vs EMA50 on M1 ---
    if settings.get("trend", True):
        e20 = _ema(closes, 20)
        e50 = _ema(closes, 50)
        if e20[-1] is not None and e50[-1] is not None and e20[-2] is not None and e50[-2] is not None:
            up = e20[-1] > e50[-1] and e20[-1] >= e20[-2]
            down = e20[-1] < e50[-1] and e20[-1] <= e20[-2]
            bull = float(last["c"]) >= float(last["o"]) and float(last["c"]) >= float(prev["c"])
            bear = float(last["c"]) <= float(last["o"]) and float(last["c"]) <= float(prev["c"])
            if up and bull:
                entry = ask
                return Signal("BUY", entry, entry - stop_d, "TREND_UP")
            if down and bear:
                entry = bid
                return Signal("SELL", entry, entry + stop_d, "TREND_DOWN")

    # --- Force idle momentum ---
    if settings.get("force_idle", True) and body >= a * 0.05:
        if float(last["c"]) > float(prev["c"]):
            entry = ask
            return Signal("BUY", entry, entry - stop_d, "FORCE_UP")
        if float(last["c"]) < float(prev["c"]):
            entry = bid
            return Signal("SELL", entry, entry + stop_d, "FORCE_DOWN")

    return None


def manage_sl(
    side: str,
    entry: float,
    price: float,
    current_sl: float,
    atr_v: float,
    settings: dict[str, Any],
) -> float | None:
    """Return new SL if trail/BE should tighten, else None."""
    a = atr_v
    if a <= 0:
        return None
    be_trig = float(settings.get("be_start_atr") or 0.75) * a
    be_off = float(settings.get("be_offset_atr") or 0.05) * a
    trail_start = float(settings.get("trail_start_atr") or 0.50) * a
    trail_lock = float(settings.get("trail_lock_atr") or 0.75) * a

    if side == "BUY":
        profit = price - entry
        candidate = current_sl
        if profit >= be_trig:
            candidate = max(candidate, entry + be_off)
        if profit >= max(trail_start, trail_lock):
            candidate = max(candidate, price - trail_lock)
        if candidate > current_sl + 1e-12:
            return candidate
        return None

    profit = entry - price
    candidate = current_sl if current_sl > 0 else entry + 1000 * a
    # for sell, SL above price; missing SL → treat as wide
    if current_sl <= 0:
        current_sl = entry + 10 * a
        candidate = current_sl
    if profit >= be_trig:
        candidate = min(candidate, entry - be_off)
    if profit >= max(trail_start, trail_lock):
        candidate = min(candidate, price + trail_lock)
    if candidate < current_sl - 1e-12:
        return candidate
    return None
