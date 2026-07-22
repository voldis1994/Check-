"""ATR-grid trailing unit tests."""

from __future__ import annotations

import pytest

from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs, price_tolerance
from checktrader.position_management.atr_grid_trailing import (
    atr_step_price,
    compute_grid_stop_loss,
    count_jump_steps,
    snap_to_reached_grid,
)
from tests.fixtures.helpers import EURUSD_SPECS


def test_atr_step_rounds_to_tick() -> None:
    # ATR=0.050, step_atr=0.20 → 0.010, already on tick
    assert atr_step_price(atr=0.050, trailing_step_atr=0.20, specs=EURUSD_SPECS) == pytest.approx(0.010)


def test_forex_tick_size_rounding() -> None:
    raw = atr_step_price(atr=0.00123, trailing_step_atr=0.20, specs=EURUSD_SPECS)
    assert abs(raw / EURUSD_SPECS.tick_size - round(raw / EURUSD_SPECS.tick_size)) < 1e-9


def test_natural_gas_tick_size_rounding() -> None:
    ng = SymbolSpecs(
        symbol="NGAS",
        digits=3,
        point=0.001,
        pip_size=0.001,
        tick_size=0.001,
        tick_value=10.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    step = atr_step_price(atr=0.050, trailing_step_atr=0.20, specs=ng)
    assert step == pytest.approx(0.010)
    assert abs(step / ng.tick_size - round(step / ng.tick_size)) < 1e-9


def test_multi_step_buy_grid() -> None:
    # atr=0.0015, step_atr=0.20 → step=0.00030
    be = 1.10020
    sl, steps = compute_grid_stop_loss(
        side=Side.BUY,
        confirmed_be_sl=be,
        current_price=1.10150,
        atr=0.0015,
        trailing_step_atr=0.20,
        specs=EURUSD_SPECS,
    )
    assert steps == 4
    assert sl == 1.10140


def test_multi_step_sell_grid() -> None:
    be = 1.10000
    sl, steps = compute_grid_stop_loss(
        side=Side.SELL,
        confirmed_be_sl=be,
        current_price=1.09850,
        atr=0.0015,
        trailing_step_atr=0.20,
        specs=EURUSD_SPECS,
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
        atr=0.0015,
        trailing_step_atr=0.20,
        specs=EURUSD_SPECS,
        tolerance=tol,
    )
    assert jump == 2


def test_never_worsen_snap() -> None:
    tol = price_tolerance(point=0.00001, digits=5)
    assert (
        snap_to_reached_grid(
            side=Side.BUY,
            anchor_sl=1.10020,
            proposed_sl=1.10010,
            atr=0.0015,
            trailing_step_atr=0.20,
            specs=EURUSD_SPECS,
            tolerance=tol,
        )
        is None
    )


def test_atr_trailing_across_digits() -> None:
    jpy = SymbolSpecs(
        symbol="USDJPY",
        digits=3,
        point=0.001,
        pip_size=0.01,
        tick_size=0.001,
        tick_value=1.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    step = atr_step_price(atr=0.050, trailing_step_atr=0.20, specs=jpy)
    assert step == pytest.approx(0.010)
    sl, steps = compute_grid_stop_loss(
        side=Side.BUY,
        confirmed_be_sl=150.100,
        current_price=150.150,
        atr=0.050,
        trailing_step_atr=0.20,
        specs=jpy,
    )
    assert steps >= 1
    assert sl is not None
    assert sl > 150.100
