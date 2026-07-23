"""ATR-native stop / trail distances (points & pips are derived, never primary).

Reference (broker point comes from MT4 meta at runtime):
  NATURALGAS  point≈0.001  ATR≈0.04  → 2.5·ATR ≈ 0.10 ≈ 100 points
  EURUSD      point≈0.00001 ATR≈0.0008 → 1.25·ATR ≈ 0.001 ≈ 10 pips
"""

from __future__ import annotations

from checktrader.domain.enums import Side


def atr_distance(atr_value: float, mult: float) -> float:
    return max(float(atr_value) * float(mult), 0.0)


def distance_points(price_distance: float, point: float) -> float:
    if point <= 0:
        return 0.0
    return abs(price_distance) / point


def clamp_stop_price(
    *,
    entry: float,
    stop: float,
    side: Side,
    atr_value: float,
    min_atr: float,
    max_atr: float,
) -> float:
    """Keep stop between min_atr·ATR and max_atr·ATR from entry."""
    if atr_value <= 0:
        return stop
    lo = atr_distance(atr_value, min_atr)
    hi = atr_distance(atr_value, max_atr)
    if hi < lo:
        lo, hi = hi, lo
    dist = abs(entry - stop)
    dist = min(max(dist, lo), hi)
    if side == Side.BUY:
        return entry - dist
    return entry + dist
