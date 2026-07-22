"""Discrete ATR-grid trailing after confirmed BE (tick-rounded price steps)."""

from __future__ import annotations

import math

from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs, round_price
from checktrader.risk.broker_constraints import min_stop_distance, round_price_to_tick
from checktrader.risk.stop_loss import atr_to_price_distance


def atr_step_price(*, atr: float, trailing_step_atr: float, specs: SymbolSpecs) -> float:
    """Price step = ATR * multiplier, rounded to broker tick_size."""
    return atr_to_price_distance(atr, trailing_step_atr, specs)


def compute_grid_stop_loss(
    *,
    side: Side,
    confirmed_be_sl: float,
    current_price: float,
    atr: float,
    trailing_step_atr: float,
    specs: SymbolSpecs,
) -> tuple[float | None, int]:
    step = atr_step_price(atr=atr, trailing_step_atr=trailing_step_atr, specs=specs)
    if step <= 0:
        return None, 0
    min_distance = min_stop_distance(specs)
    if side is Side.BUY:
        max_allowed = current_price - min_distance
        if max_allowed <= confirmed_be_sl:
            return None, 0
        steps = int(math.floor((max_allowed - confirmed_be_sl) / step + 1e-12))
        while steps >= 1:
            candidate = round_price_to_tick(confirmed_be_sl + steps * step, float(specs.tick_size))
            candidate = round_price(candidate, specs.digits)
            if candidate <= max_allowed:
                return candidate, steps
            steps -= 1
        return None, 0
    min_allowed = current_price + min_distance
    if min_allowed >= confirmed_be_sl:
        return None, 0
    steps = int(math.floor((confirmed_be_sl - min_allowed) / step + 1e-12))
    while steps >= 1:
        candidate = round_price_to_tick(confirmed_be_sl - steps * step, float(specs.tick_size))
        candidate = round_price(candidate, specs.digits)
        if candidate >= min_allowed:
            return candidate, steps
        steps -= 1
    return None, 0


def distance_stop_loss(
    *,
    side: Side,
    current_price: float,
    atr: float,
    trailing_distance_atr: float,
    specs: SymbolSpecs,
) -> float | None:
    """SL at ``trailing_distance_atr * ATR`` from current price."""
    dist = atr_to_price_distance(atr, trailing_distance_atr, specs)
    if dist <= 0:
        return None
    min_distance = min_stop_distance(specs)
    if dist + 1e-12 < min_distance:
        return None
    if side is Side.BUY:
        candidate = round_price_to_tick(current_price - dist, float(specs.tick_size))
        return round_price(candidate, specs.digits)
    candidate = round_price_to_tick(current_price + dist, float(specs.tick_size))
    return round_price(candidate, specs.digits)


def snap_to_reached_grid(
    *,
    side: Side,
    anchor_sl: float,
    proposed_sl: float,
    atr: float,
    trailing_step_atr: float,
    specs: SymbolSpecs,
    tolerance: float,
) -> float | None:
    step = atr_step_price(atr=atr, trailing_step_atr=trailing_step_atr, specs=specs)
    if step <= 0:
        return None
    if side is Side.BUY:
        if proposed_sl <= anchor_sl + tolerance:
            return None
        steps = int(math.floor((proposed_sl - anchor_sl) / step + 1e-12))
        if steps < 1:
            return None
        return round_price(round_price_to_tick(anchor_sl + steps * step, float(specs.tick_size)), specs.digits)
    if proposed_sl >= anchor_sl - tolerance:
        return None
    steps = int(math.floor((anchor_sl - proposed_sl) / step + 1e-12))
    if steps < 1:
        return None
    return round_price(round_price_to_tick(anchor_sl - steps * step, float(specs.tick_size)), specs.digits)


def count_jump_steps(
    *,
    side: Side,
    previous_sl: float,
    applied_sl: float,
    atr: float,
    trailing_step_atr: float,
    specs: SymbolSpecs,
    tolerance: float,
) -> int:
    step = atr_step_price(atr=atr, trailing_step_atr=trailing_step_atr, specs=specs)
    if step <= 0:
        return 0
    jump = int(round(abs(applied_sl - previous_sl) / step))
    if jump < 1:
        return 0
    expected = (
        round_price(round_price_to_tick(previous_sl + jump * step, float(specs.tick_size)), specs.digits)
        if side is Side.BUY
        else round_price(round_price_to_tick(previous_sl - jump * step, float(specs.tick_size)), specs.digits)
    )
    if abs(expected - applied_sl) > tolerance:
        return 0
    return jump


def favorable_price_move(*, side: Side, open_price: float, current_price: float) -> float:
    if side is Side.BUY:
        return float(current_price) - float(open_price)
    return float(open_price) - float(current_price)
