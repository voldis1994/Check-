"""ATR-adaptive stop / trail distances (volatility-native).

Hard points/pips are NOT the sizing source. ATR adapts per symbol.
If ATR is corrupt (e.g. EURUSD SL at ~294 pips), sanitize against price.
Points/pips helpers are display-only for the audit tape.
"""

from __future__ import annotations

from checktrader.config.models import ManagementConfig, StrategiesConfig
from checktrader.domain.enums import Side
from checktrader.domain.models import Candle, SymbolSpecs
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import atr as atr_indicator


_FX_MARKERS = ("EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "XAU", "XAG")


def uses_pip_quotation(specs: SymbolSpecs) -> bool:
    """FX (5-digit / JPY 3-digit) vs commodities (points)."""
    if specs.digits >= 5:
        return True
    if 0 < specs.point <= 0.0001:
        return True
    sym = (specs.symbol or "").upper().replace(".", "").replace("_", "")
    if specs.digits == 3 and any(m in sym for m in _FX_MARKERS):
        if len(sym) <= 8 and not any(x in sym for x in ("GAS", "OIL", "BRENT", "WTI", "NATG")):
            return True
    return False


def pip_size(specs: SymbolSpecs) -> float:
    if specs.point <= 0:
        return max(specs.pip_size, 0.0)
    if uses_pip_quotation(specs):
        return specs.point * 10.0
    return specs.point


def sync_pip_size(specs: SymbolSpecs) -> None:
    if specs.point <= 0:
        return
    specs.pip_size = pip_size(specs)


def atr_distance(atr_value: float | None, mult: float) -> float:
    if atr_value is None or atr_value <= 0 or mult <= 0:
        return 0.0
    return float(atr_value) * float(mult)


def distance_points(price_distance: float, point: float) -> float:
    if point <= 0:
        return 0.0
    return abs(price_distance) / point


def distance_pips(price_distance: float, specs: SymbolSpecs) -> float:
    ps = pip_size(specs)
    if ps <= 0:
        return 0.0
    return abs(price_distance) / ps


def sanitize_atr(
    atr_value: float | None,
    *,
    mid: float | None,
    specs: SymbolSpecs,
) -> float | None:
    """
    Data-quality only: reject ATR that cannot be real vs mid price.

    Live bug: ATR≈0.029 on EURUSD (~2.6% of price) → SL hundreds of pips.
    Sizing itself is always force_stop_atr · ATR — never a pip/point target.
    If ATR/mid is absurd, replace with a price-fraction estimate (still price-native).
    """
    if atr_value is None or atr_value <= 0:
        return None
    a = float(atr_value)
    if mid is None or mid <= 0:
        return a
    ratio = a / mid
    if uses_pip_quotation(specs):
        # ATR > 0.3% of mid ⇒ corrupt feed / wrong scale
        if ratio > 0.003:
            return mid * 0.001
        return a
    # Commodities: ATR > 5% of mid ⇒ corrupt
    if ratio > 0.05:
        return mid * 0.015
    return a


def robust_atr(candles: list[Candle], period: int = 14) -> float | None:
    """Wilder ATR with spike guard vs recent median."""
    bars = closed_bars(candles)
    if len(bars) < period + 1:
        return None
    series = [float(v) for v in atr_indicator(bars, period) if v is not None and v > 0]
    if not series:
        return None
    last = series[-1]
    window = series[-min(20, len(series)) :]
    med = sorted(window)[len(window) // 2]
    if med <= 0:
        return last
    return min(last, med * 1.35)


def atr_for_stops(
    *,
    m15: list[Candle] | None = None,
    m5: list[Candle] | None = None,
    m1: list[Candle] | None = None,
    period: int = 14,
    mid: float | None = None,
    specs: SymbolSpecs | None = None,
) -> float | None:
    """Prefer M1 ATR (execution TF), then M5, then M15 — sanitized for the symbol."""
    raw: float | None = None
    for series in (m1, m5, m15):
        if not series:
            continue
        value = robust_atr(series, period)
        if value is not None and value > 0:
            raw = value
            break
    if raw is None:
        return None
    if specs is None:
        return raw
    return sanitize_atr(raw, mid=mid, specs=specs)


def stop_target_distance(
    specs: SymbolSpecs,
    strategies: StrategiesConfig,
    atr_value: float | None,
    *,
    mid: float | None = None,
) -> float:
    """Initial SL = force_stop_atr · ATR (price volatility). No pip/point cap."""
    a = sanitize_atr(atr_value, mid=mid, specs=specs)
    return atr_distance(a, strategies.force_stop_atr)


def trail_lock_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
    *,
    mid: float | None = None,
) -> float:
    a = sanitize_atr(atr_value, mid=mid, specs=specs)
    return atr_distance(a, config.trailing_lock_atr)


def trail_start_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
    *,
    mid: float | None = None,
) -> float:
    a = sanitize_atr(atr_value, mid=mid, specs=specs)
    return atr_distance(a, config.trailing_start_atr)


def breakeven_trigger_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
    *,
    mid: float | None = None,
) -> float:
    a = sanitize_atr(atr_value, mid=mid, specs=specs)
    return atr_distance(a, config.breakeven_trigger_atr)


def clamp_stop_price(
    *,
    entry: float,
    stop: float,
    side: Side,
    atr_value: float,
    min_atr: float,
    max_atr: float,
    specs: SymbolSpecs | None = None,
    strategies: StrategiesConfig | None = None,
) -> float:
    """Clamp structure stop into [min_atr, max_atr] · sanitized ATR band."""
    a = float(atr_value)
    if specs is not None:
        cleaned = sanitize_atr(a, mid=entry, specs=specs)
        a = float(cleaned) if cleaned is not None else a
    if a <= 0:
        return stop
    lo = atr_distance(a, min_atr)
    hi = atr_distance(a, max_atr)
    if hi < lo:
        lo, hi = hi, lo
    # Absolute safety rail: never wider than max_atr band after sanitize
    dist = abs(entry - stop)
    dist = min(max(dist, lo), hi)
    if side == Side.BUY:
        return entry - dist
    return entry + dist
