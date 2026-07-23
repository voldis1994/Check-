"""Digit-aware stop distances: POINTS for 2/4-digit, PIPS for 3/5-digit FX.

NATURALGAS (often digits=3/4, point=0.001):
  100 points = 100 * 0.001 = 0.10

EURUSD (digits=5, point=0.00001):
  10 pips = 10 * (10*point) = 10 * 0.0001 = 0.001
  (= 100 broker points — same human intent, different unit)

ATR only clamps so quiet/wild markets stay sane.
"""

from __future__ import annotations

from checktrader.config.models import ManagementConfig, StrategiesConfig
from checktrader.domain.enums import Side
from checktrader.domain.models import SymbolSpecs


_FX_MARKERS = ("EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "XAU", "XAG")


def uses_pip_quotation(specs: SymbolSpecs) -> bool:
    """
    5-digit FX → pips.
    3-digit FX (JPY) → pips.
    NATURALGAS / most commodities (2–4 digit, no FX code) → points.
    """
    if specs.digits >= 5:
        return True
    if 0 < specs.point <= 0.0001:
        return True
    sym = (specs.symbol or "").upper().replace(".", "").replace("_", "")
    if specs.digits == 3 and any(m in sym for m in _FX_MARKERS):
        # Avoid treating NATURALGAS as FX (no EUR/USD/... marker as currency pair).
        # USDJPY / EURJPY etc. contain markers.
        # NATURALGAS contains neither as a 3-letter FX code at pair positions — "GAS" only.
        # But "USD" could appear in weird symbols; require pair-like length.
        if len(sym) <= 8 and not any(x in sym for x in ("GAS", "OIL", "BRENT", "WTI", "NATG")):
            return True
    return False


def pip_size(specs: SymbolSpecs) -> float:
    """True pip size from live specs (never trust stale config pip_size alone)."""
    if specs.point <= 0:
        return max(specs.pip_size, 0.0)
    if uses_pip_quotation(specs):
        # 5-digit FX / 3-digit JPY: pip = 10 * point
        return specs.point * 10.0
    # Commodities / 2–4 digit: treat pip_size == point for unit math
    return specs.point


def sync_pip_size(specs: SymbolSpecs) -> None:
    """Rewrite specs.pip_size after broker digits/point arrive."""
    if specs.point <= 0:
        return
    specs.pip_size = pip_size(specs)


def unit_price_distance(specs: SymbolSpecs, *, points: float, pips: float) -> float:
    """Human target → price distance using the right unit for this symbol."""
    if uses_pip_quotation(specs):
        return float(pips) * pip_size(specs)
    return float(points) * float(specs.point)


def atr_distance(atr_value: float, mult: float) -> float:
    return max(float(atr_value) * float(mult), 0.0)


def distance_points(price_distance: float, point: float) -> float:
    if point <= 0:
        return 0.0
    return abs(price_distance) / point


def distance_pips(price_distance: float, specs: SymbolSpecs) -> float:
    ps = pip_size(specs)
    if ps <= 0:
        return 0.0
    return abs(price_distance) / ps


def atr_clamp(dist: float, atr_value: float | None, min_atr: float, max_atr: float) -> float:
    if atr_value is None or atr_value <= 0:
        return max(dist, 0.0)
    lo = atr_distance(atr_value, min_atr)
    hi = atr_distance(atr_value, max_atr)
    if hi < lo:
        lo, hi = hi, lo
    return min(max(dist, lo), hi)


def stop_target_distance(
    specs: SymbolSpecs,
    strategies: StrategiesConfig,
    atr_value: float | None,
) -> float:
    """Initial SL distance: 100 points (NG) or 10 pips (EURUSD), ATR-clamped."""
    raw = unit_price_distance(
        specs,
        points=strategies.stop_target_points,
        pips=strategies.stop_target_pips,
    )
    return atr_clamp(raw, atr_value, strategies.min_stop_atr, strategies.force_stop_atr)


def trail_lock_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
) -> float:
    raw = unit_price_distance(
        specs,
        points=config.trailing_lock_points,
        pips=config.trailing_lock_pips,
    )
    # Soft ATR band so lock tracks volatility without ignoring digits
    return atr_clamp(raw, atr_value, config.trail_min_atr, config.trail_max_atr)


def trail_start_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
) -> float:
    raw = unit_price_distance(
        specs,
        points=config.trailing_start_points,
        pips=config.trailing_start_pips,
    )
    return atr_clamp(raw, atr_value, 0.0, config.trail_max_atr)


def breakeven_trigger_distance(
    specs: SymbolSpecs,
    config: ManagementConfig,
    atr_value: float | None,
) -> float:
    raw = unit_price_distance(
        specs,
        points=config.breakeven_trigger_points,
        pips=config.breakeven_trigger_pips,
    )
    return atr_clamp(raw, atr_value, 0.0, config.trail_max_atr)


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
    """Clamp structure stop into the digit-aware target band (fallback: ATR-only)."""
    if specs is not None and strategies is not None:
        target = stop_target_distance(specs, strategies, atr_value)
        # Allow structure between min ATR and the digit target (or max ATR).
        lo = atr_distance(atr_value, min_atr) if atr_value > 0 else target * 0.5
        hi = max(target, atr_distance(atr_value, max_atr) if atr_value > 0 else target)
        dist = abs(entry - stop)
        dist = min(max(dist, lo), hi)
    else:
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
