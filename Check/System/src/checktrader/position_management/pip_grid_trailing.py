"""Discrete pip-grid trailing after confirmed BE."""

from __future__ import annotations

import math

from checktrader.domain.enums import Side
from checktrader.domain.money import pip_step_price, round_price


def compute_grid_stop_loss(
    *,
    side: Side,
    confirmed_be_sl: float,
    current_price: float,
    trailing_step_pips: float,
    pip_size: float,
    digits: int,
    point: float,
    stop_level_points: int,
    freeze_level_points: int,
) -> tuple[float | None, int]:
    step = pip_step_price(trailing_step_pips=trailing_step_pips, pip_size=pip_size)
    if step <= 0:
        return None, 0
    min_distance = max(stop_level_points, freeze_level_points) * point
    if side is Side.BUY:
        max_allowed = current_price - min_distance
        if max_allowed <= confirmed_be_sl:
            return None, 0
        steps = int(math.floor((max_allowed - confirmed_be_sl) / step + 1e-12))
        while steps >= 1:
            candidate = round_price(confirmed_be_sl + steps * step, digits)
            if candidate <= max_allowed:
                return candidate, steps
            steps -= 1
        return None, 0
    min_allowed = current_price + min_distance
    if min_allowed >= confirmed_be_sl:
        return None, 0
    steps = int(math.floor((confirmed_be_sl - min_allowed) / step + 1e-12))
    while steps >= 1:
        candidate = round_price(confirmed_be_sl - steps * step, digits)
        if candidate >= min_allowed:
            return candidate, steps
        steps -= 1
    return None, 0


def snap_to_reached_grid(
    *,
    side: Side,
    anchor_sl: float,
    proposed_sl: float,
    trailing_step_pips: float,
    pip_size: float,
    digits: int,
    tolerance: float,
) -> float | None:
    step = pip_step_price(trailing_step_pips=trailing_step_pips, pip_size=pip_size)
    if step <= 0:
        return None
    if side is Side.BUY:
        if proposed_sl <= anchor_sl + tolerance:
            return None
        steps = int(math.floor((proposed_sl - anchor_sl) / step + 1e-12))
        if steps < 1:
            return None
        return round_price(anchor_sl + steps * step, digits)
    if proposed_sl >= anchor_sl - tolerance:
        return None
    steps = int(math.floor((anchor_sl - proposed_sl) / step + 1e-12))
    if steps < 1:
        return None
    return round_price(anchor_sl - steps * step, digits)


def count_jump_steps(
    *,
    side: Side,
    previous_sl: float,
    applied_sl: float,
    trailing_step_pips: float,
    pip_size: float,
    digits: int,
    tolerance: float,
) -> int:
    step = pip_step_price(trailing_step_pips=trailing_step_pips, pip_size=pip_size)
    jump = int(round(abs(applied_sl - previous_sl) / step))
    if jump < 1:
        return 0
    expected = (
        round_price(previous_sl + jump * step, digits)
        if side is Side.BUY
        else round_price(previous_sl - jump * step, digits)
    )
    if abs(expected - applied_sl) > tolerance:
        return 0
    return jump
