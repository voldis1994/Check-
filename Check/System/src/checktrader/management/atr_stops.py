"""ATR-adaptive stop / trail distances (volatility-native).

Hard points/pips are NOT used for sizing. ATR already adapts to
NATURALGAS vs EURUSD because it is measured in that symbol's price.

Points/pips helpers exist only for audit/display after the ATR distance
is computed (so you can read “≈X points” or “≈Y pips” on the tape).
"""

from __future__ import annotations

from checktrader.config.models import ManagementConfig, StrategiesConfig
from checktrader.domain.enums import Side
from checktrader.domain.models import SymbolSpecs


_FX_MARKERS = ("EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "XAU", "XAG")


def uses_pip_quotation(specs: SymbolSpecs) -> bool:
    """Display helper: show pips for FX, points for commodities."""
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


def atr_distance(atr_value: float, mult: float) -> float:
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


def stop_target_distance(
    specs: SymbolSpecs,
    strategies: StrategiesConfig,
    atr_value: float | None,
) -> float:
    """Initial SL = force_stop_atr · ATR (fully adaptive)."""
    del specs  # digits unused for sizing — ATR carries the scale
    return atr_distance(atr_value or 0.0, strategies.force_stop_atr)


def trail_lock_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
) -> float:
    del specs
    return atr_distance(atr_value or 0.0, config.trailing_lock_atr)


def trail_start_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
) -> float:
    del specs
    return atr_distance(atr_value or 0.0, config.trailing_start_atr)


def breakeven_trigger_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
) -> float:
    del specs
    return atr_distance(atr_value or 0.0, config.breakeven_trigger_atr)


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
    """Clamp structure stop into [min_atr, max_atr] · ATR band."""
    del specs, strategies
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
