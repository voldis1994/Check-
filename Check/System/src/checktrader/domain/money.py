"""Money and price helpers."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import Side


@dataclass(frozen=True, slots=True)
class SymbolSpecs:
    symbol: str
    digits: int
    point: float
    pip_size: float
    tick_size: float
    tick_value: float
    minimum_lot: float
    maximum_lot: float
    lot_step: float
    stop_level_points: int
    freeze_level_points: int


def price_tolerance(*, point: float, digits: int, points: int = 2) -> float:
    digit_eps = 10 ** (-digits) if digits > 0 else 0.0
    return max(point * max(points, 1), digit_eps, 1e-12)


def round_price(price: float, digits: int) -> float:
    return round(float(price), int(digits))


def money_per_price_unit(*, tick_value: float, tick_size: float, volume: float) -> float:
    if tick_value <= 0 or tick_size <= 0 or volume <= 0:
        raise ValueError("tick_value, tick_size and volume must be > 0")
    return (tick_value / tick_size) * volume


def compute_net_profit(*, profit: float, swap: float, commission: float) -> float:
    return float(profit) + float(swap) + float(commission)


def sl_improves(*, side: Side, current_sl: float, proposed_sl: float, tolerance: float) -> bool:
    if current_sl <= 0 and proposed_sl > 0:
        return True
    if side is Side.BUY:
        return proposed_sl > current_sl + tolerance
    return proposed_sl < current_sl - tolerance


def pip_step_price(*, trailing_step_pips: float, pip_size: float) -> float:
    """Legacy helper for display/spread math. Trailing uses ATR × tick_size instead."""
    return float(trailing_step_pips) * float(pip_size)
