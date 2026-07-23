"""M1 trend + breakout. SL distance = points from account (no ATR)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Signal:
    side: str
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


def points_to_price(points: float, point: float) -> float:
    return float(points) * float(point)


def evaluate(market: dict[str, Any], account: dict[str, Any], global_cfg: dict[str, Any]) -> Signal | None:
    bars = market.get("bars_m1") or []
    if len(bars) < 30:
        return None
    closes = [float(b["c"]) for b in bars]
    bid = float(market.get("bid") or closes[-1])
    ask = float(market.get("ask") or closes[-1])
    point = float(market.get("point") or 0.00001)
    if point <= 0:
        point = 0.00001

    sl_pts = float(account.get("sl_points") or 0)
    if sl_pts <= 0:
        return None  # user must set SL points per account
    stop_d = points_to_price(sl_pts, point)

    last = bars[-1]
    prev = bars[-2]

    # rough box width proxy in points for breakout filter
    if global_cfg.get("breakout", True):
        look = bars[-21:-1]
        if len(look) >= 15:
            box_hi = max(float(b["h"]) for b in look)
            box_lo = min(float(b["l"]) for b in look)
            width = box_hi - box_lo
            if width > points_to_price(20, point):
                c = float(last["c"])
                if c > box_hi and c >= float(last["o"]):
                    entry = ask
                    return Signal("BUY", entry, entry - stop_d, "BREAKOUT_UP")
                if c < box_lo and c <= float(last["o"]):
                    entry = bid
                    return Signal("SELL", entry, entry + stop_d, "BREAKOUT_DOWN")

    if global_cfg.get("trend", True):
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

    return None


def manage_sl(
    side: str,
    entry: float,
    price: float,
    current_sl: float,
    point: float,
    account: dict[str, Any],
) -> float | None:
    """BE + trail using per-account POINTS (not ATR)."""
    if point <= 0:
        return None
    be_start = points_to_price(float(account.get("be_start_points") or 0), point)
    be_off = points_to_price(float(account.get("be_offset_points") or 0), point)
    trail_start = points_to_price(float(account.get("trail_start_points") or 0), point)
    trail_lock = points_to_price(float(account.get("trail_lock_points") or 0), point)

    if side == "BUY":
        profit = price - entry
        candidate = current_sl
        if be_start > 0 and profit >= be_start:
            candidate = max(candidate, entry + be_off)
        if trail_start > 0 and trail_lock > 0 and profit >= trail_start:
            candidate = max(candidate, price - trail_lock)
        if candidate > current_sl + point * 0.1:
            return candidate
        return None

    profit = entry - price
    if current_sl <= 0:
        current_sl = entry + points_to_price(float(account.get("sl_points") or 100), point)
    candidate = current_sl
    if be_start > 0 and profit >= be_start:
        candidate = min(candidate, entry - be_off)
    if trail_start > 0 and trail_lock > 0 and profit >= trail_start:
        candidate = min(candidate, price + trail_lock)
    if candidate < current_sl - point * 0.1:
        return candidate
    return None
