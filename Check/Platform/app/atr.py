"""ATR helpers — M1 native."""

from __future__ import annotations


def atr(bars: list[dict], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(bars)):
        h = float(bars[i]["h"])
        l = float(bars[i]["l"])
        pc = float(bars[i - 1]["c"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    # Wilder smooth
    val = sum(trs[:period]) / period
    for tr in trs[period:]:
        val = (val * (period - 1) + tr) / period
    return val if val > 0 else None


def sanitize(atr_v: float, mid: float) -> float:
    if mid <= 0:
        return atr_v
    if atr_v / mid > 0.003:  # absurd FX ATR
        return mid * 0.001
    if atr_v / mid > 0.05:  # absurd commodity
        return mid * 0.015
    return atr_v
