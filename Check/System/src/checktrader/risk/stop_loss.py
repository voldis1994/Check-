"""ATR-based stop distance → absolute price, tick-rounded, stop/freeze checked."""

from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs
from checktrader.risk.broker_constraints import min_stop_distance, round_price_to_tick


def atr_to_price_distance(atr: float, atr_mult: float, specs: SymbolSpecs) -> float:
    """Convert ATR multiples to absolute price distance, rounded to tick_size."""
    raw = float(atr) * float(atr_mult)
    if raw <= 0 or float(specs.tick_size) <= 0:
        return 0.0
    return round_price_to_tick(raw, float(specs.tick_size))


def build_stop_loss(
    *,
    side: Side,
    entry_price: float,
    atr: float,
    maximum_stop_atr: float,
    specs: SymbolSpecs,
) -> float | None:
    """SL at ``maximum_stop_atr * ATR`` from entry, tick-rounded; None if invalid."""
    dist = atr_to_price_distance(atr, maximum_stop_atr, specs)
    if dist <= 0:
        return None
    if dist + 1e-12 < min_stop_distance(specs):
        return None
    if side is Side.BUY:
        sl = round_price_to_tick(entry_price - dist, float(specs.tick_size))
        if sl >= entry_price:
            return None
        return sl
    sl = round_price_to_tick(entry_price + dist, float(specs.tick_size))
    if sl <= entry_price:
        return None
    return sl


def money_to_price_offset(
    *,
    money: float,
    lot: float,
    tick_size: float,
    tick_value: float,
) -> float:
    """Price distance that yields approximately ``money`` PnL for ``lot``."""
    if lot <= 0 or tick_size <= 0 or tick_value <= 0:
        return 0.0
    ticks = money / (lot * tick_value)
    return ticks * tick_size
