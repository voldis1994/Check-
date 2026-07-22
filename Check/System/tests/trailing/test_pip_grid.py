"""Pip-grid trailing unit tests."""

from __future__ import annotations

import pytest

from checktrader.domain.enums import Side
from checktrader.domain.money import pip_step_price, price_tolerance
from checktrader.position_management.pip_grid_trailing import (
    compute_grid_stop_loss,
    count_jump_steps,
    snap_to_reached_grid,
)


def test_eurusd_three_pips_is_00030() -> None:
    assert pip_step_price(trailing_step_pips=3.0, pip_size=0.0001) == pytest.approx(0.00030)


def test_multi_step_buy_grid() -> None:
    be = 1.10020
    # price far enough for 3 steps: be + 3*0.00030 = 1.10110, need price above that + stop level
    sl, steps = compute_grid_stop_loss(
        side=Side.BUY,
        confirmed_be_sl=be,
        current_price=1.10150,
        trailing_step_pips=3.0,
        pip_size=0.0001,
        digits=5,
        point=0.00001,
        stop_level_points=0,
        freeze_level_points=0,
    )
    assert steps == 4  # floor((1.10150-1.10020)/0.00030)=floor(4.333)=4 → 1.10140
    assert sl == 1.10140


def test_multi_step_sell_grid() -> None:
    be = 1.10000
    sl, steps = compute_grid_stop_loss(
        side=Side.SELL,
        confirmed_be_sl=be,
        current_price=1.09850,
        trailing_step_pips=3.0,
        pip_size=0.0001,
        digits=5,
        point=0.00001,
        stop_level_points=0,
        freeze_level_points=0,
    )
    assert steps >= 2
    assert sl is not None
    assert sl < be


def test_jump_steps_count() -> None:
    tol = price_tolerance(point=0.00001, digits=5)
    jump = count_jump_steps(
        side=Side.BUY,
        previous_sl=1.10020,
        applied_sl=1.10080,
        trailing_step_pips=3.0,
        pip_size=0.0001,
        digits=5,
        tolerance=tol,
    )
    assert jump == 2


def test_never_worsen_snap() -> None:
    tol = price_tolerance(point=0.00001, digits=5)
    # proposed below anchor for BUY → None
    assert (
        snap_to_reached_grid(
            side=Side.BUY,
            anchor_sl=1.10020,
            proposed_sl=1.10010,
            trailing_step_pips=3.0,
            pip_size=0.0001,
            digits=5,
            tolerance=tol,
        )
        is None
    )


def test_no_interstitial_money_steps_only_pip_grid() -> None:
    """After BE, only discrete pip multiples — not arbitrary money offsets."""
    be = 1.10020
    step = 0.00030
    for price in (1.10040, 1.10055, 1.10070):
        sl, steps = compute_grid_stop_loss(
            side=Side.BUY,
            confirmed_be_sl=be,
            current_price=price,
            trailing_step_pips=3.0,
            pip_size=0.0001,
            digits=5,
            point=0.00001,
            stop_level_points=0,
            freeze_level_points=0,
        )
        if sl is None:
            continue
        assert abs((sl - be) / step - round((sl - be) / step)) < 1e-9
        assert steps >= 1
